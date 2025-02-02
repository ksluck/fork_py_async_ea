#! /usr/bin/python3
import sys
import random as rd
import multiprocessing as mp
from nestable_pool import NestablePool
from deap import algorithms
from exception import LogExceptions
import builtins

def print(*objects):
    string = "" 
    for o in objects:
        string += str(o) + " "
    builtins.print(string,flush=True)

def generate(parents,toolbox,size):
        ''' generate takes a list already evaluated parents and the size of the offspring to generate'''

        #select the individuals from the offspring will be produced
        selected_parents = toolbox.parents_select(parents, size)
    
        # Clone the selected individuals
        offspring = list(map(toolbox.clone, selected_parents))

        # Apply crossover and mutation on the offspring
        offspring = algorithms.varAnd(offspring, toolbox, 0.1, 0.2)

        return offspring

class AsynchEA:
    def __init__(self,pop_size,nb_workers,sync=0):
        self.pop_size = pop_size
        self.nbr_ind_to_wait = int(pop_size)*sync
        if sync == 0:
            self.nbr_ind_to_wait = 1
        print("number ind to wait:", self.nbr_ind_to_wait)
        self.parents = []
        self.pop = []
        self.evaluated_ind = []
        self.iteration = 0
        self.max_workers = nb_workers
        self.pool = NestablePool(processes=nb_workers)#,maxtasksperchild=100)
        self.in_evaluation = []
        self.workers_failed = False

    def remove(self,select):
        dead = select(self.parents,len(self.parents)-self.pop_size)
        for ind in dead:
            self.parents.remove(ind) 
            del ind

    def worker_callback(self,results):     
        if results == None:
            self.workers_failed = True
        else:
            self.evaluated_ind.append(results)
            self.in_evaluation.remove(results)
 


    def asynch_map(self,eval):
        for ind in self.pop:
            is_new_ind = True
            for e_ind in self.in_evaluation + self.evaluated_ind:
                if e_ind == ind:
                    is_new_ind = False
                    break
            if is_new_ind and len(self.in_evaluation) < self.max_workers:
                #print("ind",ind.index,"send to evaluation")
                self.in_evaluation.append(ind)
                self.pool.apply_async(LogExceptions(eval),(ind,),callback=self.worker_callback)
            if len(self.in_evaluation) >= self.max_workers:
                break

    #sequential execution. Use only for debugging
    def seq_map(self,eval):
        for ind in self.pop:
            results = eval(ind)
            self.evaluated_ind.append(results)
            
    def update(self,eval):
        # Evaluate the individuals with asynch map. Evaluate as to return a ref to the ind at the end
        #self.seq_map(eval)
        self.asynch_map(eval)
        if self.workers_failed:
            self.terminate()
            sys.exit("Exiting because of workers crash")

        if len(self.evaluated_ind) >= self.nbr_ind_to_wait:
            print("number individual evaluated",len(self.evaluated_ind))
            for e_ind in self.evaluated_ind:
                for i in range(len(self.pop)):
                    if self.pop[i] == e_ind:
                        self.pop[i] = e_ind
                        break
            del self.evaluated_ind
            self.evaluated_ind = []
    
        new_parents = [ind for ind in self.pop if ind.fitness.valid]
        if(len(new_parents) > 0):
            print("new_parents",[ind.index for ind in new_parents])
        for ind in new_parents:
            self.pop.remove(ind)

        return new_parents

    def init(self,toolbox):
        #initialisation
        self.pop = toolbox.population(self.pop_size)
        while len(self.parents) < self.pop_size:
            new_par = self.update(toolbox.eval)
            self.parents = self.parents + new_par
            if(len(new_par) > 0):
                print("init progress:",float(len(self.parents))/float(self.pop_size)*100,"%")
        assert(len(self.pop) == 0)
        self.pop = toolbox.generate(self.parents,toolbox,self.pop_size)
        print(len(self.pop))
        toolbox.extra(toolbox,self.parents,self.iteration)
        return self.parents

    def step(self,toolbox):
        #update - evaluation
        new_par = self.update(toolbox.eval)
        if len(new_par) > 0:
            self.parents = self.parents + new_par

            #survival
            self.remove(toolbox.death_select)
        
            #selection - mutation - crossover
            offspring = toolbox.generate(self.parents,toolbox,self.pop_size - len(self.pop))
            self.pop = self.pop + offspring
        
            self.iteration += 1

            toolbox.extra(toolbox,self.parents,self.iteration)

        return self.parents, new_par

    def terminate(self):
        self.pool.terminate()
        self.pool.join()
