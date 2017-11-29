"""
Name:        xcs_classifierset.py
Authors:     Bao Trung
Contact:     baotrung@ecs.vuw.ac.nz
Created:     July, 2017
Description:
---------------------------------------------------------------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------------------------------------------------------------
"""

#Import Required Modules---------------------
from xcs_constants import *
from xcs_classifier import Classifier
import random
import copy
import sys
#--------------------------------------------

class ClassifierSet:
    def __init__(self, a=None):
        """ Overloaded initialization: Handles creation of a new population or a rebooted population (i.e. a previously saved population). """
        # Major Parameters
        self.pop_set = []        # List of classifiers/rules
        self.match_set = []      # List of references to rules in population that match
        self.action_set = []     # List of references to rules in population that match and has action with highest prediction payoff
        self.micro_size = 0   # Tracks the current micro population size, i.e. the population size which takes rule numerosity into account.

        # Evaluation Parameters-------------------------------
        self.mean_generality = 0.0
        self.attribute_spec_list = []
        self.attribute_acc_list = []
        self.ave_phenotype_range = 0.0

        # Set Constructors-------------------------------------
        if a==None:
            self.makePop() #Initialize a new population
        elif isinstance(a,str):
            self.rebootPop(a) #Initialize a population based on an existing saved rule population
        else:
            print("ClassifierSet: Error building population.")

    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # POPULATION CONSTRUCTOR METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def makePop(self):
        """ Initializes the rule population """
        self.pop_set = []


    def rebootPop(self, remakeFile):
        """ Remakes a previously evolved population from a saved text file. """
        print("Rebooting the following population: " + str(remakeFile)+"_RulePop.txt")
        #*******************Initial file handling**********************************************************
        dataset_list = []
        try:
            f = open(remakeFile+"_RulePop.txt", 'r')
        except Exception as inst:
            print(type(inst))
            print(inst.args)
            print(inst)
            print('cannot open', remakeFile+"_RulePop.txt")
            raise
        else:
            self.header_list = f.readline().rstrip('\n').split('\t')   #strip off first row
            for line in f:
                line_list = line.strip('\n').split('\t')
                dataset_list.append(line_list)
            f.close()

        #**************************************************************************************************
        for each in dataset_list:
            cl = Classifier(each)
            self.pop_set.append(cl)
            numerosity_ref = cons.env.format_data.numb_attributes + 3
            self.micro_size += int(each[numerosity_ref])
        print("Rebooted Rule Population has "+str(len(self.pop_set))+" Macro Pop Size.")

    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # CLASSIFIER SET CONSTRUCTOR METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def makeMatchSet(self, state, iteration, pool=None):
        """ Constructs a match set from the population. Covering is initiated if the match set is empty or total prediction of rules in match set is too low. """
        #Initial values
        do_covering = True # Covering check: Twofold (1)checks that a match is present, and (2) that total Prediction in Match Set is greater than a threshold compared to mean preadiction.
        matched_phenotype_list = []
        self.current_instance = state
        #totalPrediction = 0.0
        #totalMatchSetPrediction = 0.0
        #-------------------------------------------------------
        # MATCHING
        #-------------------------------------------------------
        cons.timer.startTimeMatching()
        if cons.multiprocessing:
            results = pool.map( self.parallelMatching, range( len( self.pop_set ) ) )
            for id in results:
                if id != None:
                    self.match_set.append( id )                 # If match - add classifier to match set
                    if self.pop_set[ id ].phenotype not in matched_phenotype_list:
                        matched_phenotype_list.append( self.pop_set[ id ].phenotype )
        else:
            for i in range( len( self.pop_set ) ):              # Go through the population
                cl = self.pop_set[i]                            # One classifier at a time
                #totalPrediction += cl.prediction * cl.numerosity
                if cl.match( state ):                             # Check for match
                    self.match_set.append( i )                  # If match - add classifier to match set
                    if cl.phenotype not in matched_phenotype_list:
                        matched_phenotype_list.append( cl.phenotype )
                    #totalMatchSetPrediction += cl.prediction * cl.numerosity
        cons.timer.stopTimeMatching()
        #if totalMatchSetPrediction * self.micro_size >= cons.phi * totalPrediction and totalPrediction > 0:
        if len( matched_phenotype_list ) >= cons.theta_mna:# and ( totalMatchSetPrediction * self.micro_size >= cons.phi * totalPrediction and totalPrediction > 0 ):
            do_covering = False
        #-------------------------------------------------------
        # COVERING
        #-------------------------------------------------------
        while do_covering:
            newCl = Classifier(iteration, state, random.choice(list(set(cons.env.format_data.action_list) - set(matched_phenotype_list))))
            self.addClassifierToPopulation( newCl )
            self.match_set.append( len(self.pop_set)-1 )  # Add covered classifier to match set
            matched_phenotype_list.append( newCl.phenotype )
            #totalMatchSetPrediction += newCl.prediction * newCl.numerosity
            #totalPrediction += newCl.prediction * newCl.numerosity
            if len( matched_phenotype_list ) >= cons.theta_mna: #totalMatchSetPrediction * self.micro_size >= cons.phi * totalPrediction and
                self.deletion( iteration )
                self.match_set = []
                do_covering = False


    def makeActionSet(self, selected_action):
        """ Constructs a correct set out of the given match set. """
        for i in range(len(self.match_set)):
            ref = self.match_set[i]
            #-------------------------------------------------------
            # DISCRETE PHENOTYPE
            #-------------------------------------------------------
            if cons.env.format_data.discrete_action:
                if self.pop_set[ref].phenotype == selected_action:
                    self.action_set.append(ref)
            #-------------------------------------------------------
            # CONTINUOUS PHENOTYPE
            #-------------------------------------------------------
            else:
                if float(selected_action) <= float(self.pop_set[ref].phenotype[1]) and float(selected_action) >= float(self.pop_set[ref].phenotype[0]):
                    self.action_set.append(ref)


    def makeEvalMatchSet(self, state):
        """ Constructs a match set for evaluation purposes which does not activate either covering or deletion. """
        for i in range(len(self.pop_set)):       # Go through the population
            cl = self.pop_set[i]                 # A single classifier
            if cl.match(state):                 # Check for match
                self.match_set.append(i)         # Add classifier to match set


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # CLASSIFIER DELETION METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def deletion(self, exploreIter):
        """ Returns the population size back to the maximum set by the user by deleting rules. """
        cons.timer.startTimeDeletion()
        while self.micro_size > cons.N:
            self.deleteFromPopulation()
        cons.timer.stopTimeDeletion()


    def deleteFromPopulation(self):
        """ Deletes one classifier in the population.  The classifier that will be deleted is chosen by roulette wheel selection
        considering the deletion vote. Returns the macro-classifier which got decreased by one micro-classifier. """
        meanFitness = self.getPopFitnessSum()/float(self.micro_size)

        #Calculate total wheel size------------------------------
        vote_sum = 0.0
        voteList = []
        for cl in self.pop_set:
            vote = cl.getDelProb(meanFitness)
            vote_sum += vote
            voteList.append(vote)
        #--------------------------------------------------------
        choicePoint = vote_sum * random.random() #Determine the choice point

        newSum=0.0
        for i in range(len(voteList)):
            cl = self.pop_set[i]
            newSum = newSum + voteList[i]
            if newSum > choicePoint: #Select classifier for deletion
                #Delete classifier----------------------------------
                cl.updateNumerosity(-1)
                self.micro_size -= 1
                if cl.numerosity < 1: # When all micro-classifiers for a given classifier have been depleted.
                    self.removeMacroClassifier(i)
                    self.deleteFromMatchSet(i)
                    self.deleteFromActionSet(i)
                return

        print("ClassifierSet: No eligible rules found for deletion in deleteFromPopulation.")
        return


    def removeMacroClassifier(self, ref):
        """ Removes the specified (macro-) classifier from the population. """
        self.pop_set.pop(ref)


    def deleteFromMatchSet(self, deleteRef):
        """ Delete reference to classifier in population, contained in self.match_set."""
        if deleteRef in self.match_set:
            self.match_set.remove(deleteRef)

        #Update match set reference list--------
        for j in range(len(self.match_set)):
            ref = self.match_set[j]
            if ref > deleteRef:
                self.match_set[j] -= 1


    def deleteFromActionSet(self, deleteRef):
        """ Delete reference to classifier in population, contained in self.action_set."""
        if deleteRef in self.action_set:
            self.action_set.remove(deleteRef)

        #Update match set reference list--------
        for j in range(len(self.action_set)):
            ref = self.action_set[j]
            if ref > deleteRef:
                self.action_set[j] -= 1


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # GENETIC ALGORITHM
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def runGA(self, exploreIter, state):
        """ The genetic discovery mechanism in XCS is controlled here. """
        #-------------------------------------------------------
        # GA RUN REQUIREMENT
        #-------------------------------------------------------
        if (exploreIter - self.getIterStampAverage()) < cons.theta_GA:  #Does the action set meet the requirements for activating the GA?
            return

        self.setIterStamps(exploreIter) #Updates the iteration time stamp for all rules in the match set (which the GA opperates in).
        changed = False

        #-------------------------------------------------------
        # SELECT PARENTS - Niche GA - selects parents from the match set
        #-------------------------------------------------------
        cons.timer.startTimeSelection()
        if cons.selectionMethod == "roulette":
            selectList = self.selectClassifierRW()
            clP1 = selectList[0]
            clP2 = selectList[1]
        elif cons.selectionMethod == "tournament":
            selectList = self.selectClassifierT()
            clP1 = selectList[0]
            clP2 = selectList[1]
        else:
            print("ClassifierSet: Error - requested GA selection method not available.")
        cons.timer.stopTimeSelection()
        clP1.updateGACount()
        clP2.updateGACount()
        #-------------------------------------------------------
        # INITIALIZE OFFSPRING
        #-------------------------------------------------------
        cl1  = Classifier(clP1, exploreIter)
        if clP2 == None:
            cl2 = Classifier(clP1, exploreIter)
        else:
            cl2 = Classifier(clP2, exploreIter)

        #-------------------------------------------------------
        # CROSSOVER OPERATOR - Uniform Crossover Implemented (i.e. all attributes have equal probability of crossing over between two parents)
        #-------------------------------------------------------
        if not cl1.equals(cl2) and random.random() < cons.chi:
            if cons.crossover_method == 'uniform':
                changed = cl1.uniformCrossover(cl2)
            elif cons.crossover_method == 'twopoint':
                changed = cl1.twoPointCrossover(cl2)

        #-------------------------------------------------------
        # INITIALIZE KEY OFFSPRING PARAMETERS
        #-------------------------------------------------------
        if changed:
            cl1.setPrediction((cl1.prediction + cl2.prediction)/2)
            cl1.setError((cl1.error + cl2.error)/2.0)
            cl1.setFitness(cons.fitnessReduction * (cl1.fitness + cl2.fitness)/2.0)
            cl2.setPrediction(cl1.prediction)
            cl2.setError(cl1.error)
            cl2.setFitness(cl1.fitness)

        cl1.setFitness(cons.fitnessReduction * cl1.fitness)
        cl2.setFitness(cons.fitnessReduction * cl2.fitness)
        #-------------------------------------------------------
        # MUTATION OPERATOR
        #-------------------------------------------------------
        nowchanged = cl1.Mutation(state)
        howaboutnow = cl2.Mutation(state)
        #-------------------------------------------------------
        # ADD OFFSPRING TO POPULATION
        #-------------------------------------------------------
        if changed or nowchanged or howaboutnow:
            self.insertDiscoveredClassifiers(cl1, cl2, clP1, clP2, exploreIter) #Subsumption
        self.deletion(exploreIter)


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # SELECTION METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def selectClassifierRW(self):
        """ Selects parents using roulette wheel selection according to the fitness of the classifiers. """
        #Prepare for actionSet set or 'niche' selection.
        setList = copy.deepcopy(self.action_set)

        if len(setList) > 2:
            selectList = [None, None]
            currentCount = 0 #Pick two parents
            #-----------------------------------------------
            while currentCount < 2:
                fitSum = self.getFitnessSum(setList)

                choiceP = random.random() * fitSum
                i=0
                sumCl = self.pop_set[setList[i]].fitness
                while choiceP > sumCl:
                    i=i+1
                    sumCl += self.pop_set[setList[i]].fitness

                selectList[currentCount] = self.pop_set[setList[i]]
                setList.remove(setList[i])
                currentCount += 1
            #-----------------------------------------------
        elif len(setList) == 2:
            selectList = [self.pop_set[setList[0]],self.pop_set[setList[1]]]
        elif len(setList) == 1:
            selectList = [self.pop_set[setList[0]],self.pop_set[setList[0]]]
        else:
            print("ClassifierSet: Error in parent selection.")

        return selectList


    def selectClassifierT(self):
        """  Selects parents using tournament selection according to the fitness of the classifiers. """
        selectList = [None, None]
        currentCount = 0
        setList = self.action_set #actionSet set is a list of reference IDs

        while currentCount < 2:
            tSize = int(len(setList)*cons.theta_sel)
            posList = random.sample(setList,tSize)

            bestF = 0
            bestC = self.action_set[0]
            for j in posList:
                if self.pop_set[j].fitness > bestF:
                    bestF = self.pop_set[j].fitness
                    bestC = j

            selectList[currentCount] = self.pop_set[bestC]
            currentCount += 1

        return selectList


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # SUBSUMPTION METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def subsumeClassifier(self, cl=None, cl1P=None, cl2P=None):
        """ Tries to subsume a classifier in the parents. If no subsumption is possible it tries to subsume it in the current set. """
        if cl1P!=None and cl1P.subsumes(cl):
            self.micro_size += 1
            cl1P.updateNumerosity(1)
        elif cl2P!=None and cl2P.subsumes(cl):
            self.micro_size += 1
            cl2P.updateNumerosity(1)
        else:
            self.addClassifierToPopulation(cl)
            #self.subsumeClassifier2(cl); #Try to subsume in the match set.


    def subsumeClassifier2(self, cl):
        """ Tries to subsume a classifier in the match set. If no subsumption is possible the classifier is simply added to the population considering
        the possibility that there exists an identical classifier. """
        choices = []
        for ref in self.match_set:
            if self.pop_set[ref].subsumes(cl):
                choices.append(ref)

        if len(choices) > 0: #Randomly pick one classifier to be subsumer
            choice = int(random.random()*len(choices))
            self.pop_set[choices[choice]].updateNumerosity(1)
            self.micro_size += 1
            return

        self.addClassifierToPopulation(cl) #If no subsumer was found, check for identical classifier, if not then add the classifier to the population


    def doActionSetSubsumption(self):
        """ Executes match set subsumption.  The match set subsumption looks for the most general subsumer classifier in the match set
        and subsumes all classifiers that are more specific than the selected one. """
        subsumer = None
        for ref in self.action_set:
            cl = self.pop_set[ref]
            if cl.isPossibleSubsumer():
                if subsumer == None or len( subsumer.specifiedAttList ) > len( cl.specifiedAttList ) or ( ( len(subsumer.specifiedAttList ) == len(cl.specifiedAttList) and random.random() < 0.5 ) ):
                    subsumer = cl

        if subsumer != None: #If a subsumer was found, subsume all more specific classifiers in the match set
            i=0
            while i < len(self.action_set):
                ref = self.action_set[i]
                if subsumer.isMoreGeneral(self.pop_set[ref]):
                    subsumer.updateNumerosity(self.pop_set[ref].numerosity)
                    self.removeMacroClassifier(ref)
                    self.deleteFromMatchSet(ref)
                    self.deleteFromActionSet(ref)
                    i = i - 1
                i = i + 1


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # OTHER KEY METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def addClassifierToPopulation(self, cl, covering = False):
        """ Adds a classifier to the set and increases the microPopSize value accordingly."""
        oldCl = None
        if not covering:
            oldCl = self.getIdenticalClassifier(cl)
        if oldCl != None: #found identical classifier
            oldCl.updateNumerosity(1)
        else:
            self.pop_set.append(cl)
        self.micro_size += 1


    def insertDiscoveredClassifiers(self, cl1, cl2, clP1, clP2, exploreIter):
        """ Inserts both discovered classifiers and activates GA subsumption if turned on. Also checks for default rule (i.e. rule with completely general condition) and
        prevents such rules from being added to the population, as it offers no predictive value within XCS. """
        #-------------------------------------------------------
        # SUBSUMPTION
        #-------------------------------------------------------
        if cons.do_subsumption:
            cons.timer.startTimeSubsumption()

            if len(cl1.specifiedAttList) > 0:
                self.subsumeClassifier(cl1, clP1, clP2)
            if len(cl2.specifiedAttList) > 0:
                self.subsumeClassifier(cl2, clP1, clP2)

            cons.timer.stopTimeSubsumption()
        #-------------------------------------------------------
        # ADD OFFSPRING TO POPULATION
        #-------------------------------------------------------
        else: #Just add the new classifiers to the population.
            if len(cl1.specifiedAttList) > 0:
                self.addClassifierToPopulation(cl1) #False passed because this is not called for a covered rule.
            if len(cl2.specifiedAttList) > 0:
                self.addClassifierToPopulation(cl2) #False passed because this is not called for a covered rule.


    def updateSets(self, exploreIter, reward):
        """ Updates all relevant parameters in the current match and match sets. """
        actionSetNumerosity = 0
        for ref in self.action_set:
            actionSetNumerosity += self.pop_set[ref].numerosity
        accuracySum = 0.0
        for ref in self.action_set:
            #self.pop_set[ref].updateExperience()
            #self.pop_set[ref].updateMatchSetSize(matchSetNumerosity)
            #if ref in self.action_set:
            self.pop_set[ref].updateActionExp()
            self.pop_set[ref].updateActionSetSize( actionSetNumerosity )
            self.pop_set[ref].updateXCSParameters( reward )
            accuracySum += self.pop_set[ref].accuracy * self.pop_set[ref].numerosity
        for ref in self.action_set:
            self.pop_set[ref].setAccuracy( 1000 * self.pop_set[ref].accuracy * self.pop_set[ref].numerosity / accuracySum )
            self.pop_set[ref].updateFitness()


    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # OTHER METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def getIterStampAverage(self):
        """ Returns the average of the time stamps in the match set. """
        sumCl=0.0
        numSum=0.0
        for i in range(len(self.action_set)):
            ref = self.action_set[i]
            sumCl += self.pop_set[ref].ga_timestamp * self.pop_set[ref].numerosity
            numSum += self.pop_set[ref].numerosity #numerosity sum of match set
        return sumCl/float(numSum)


    def setIterStamps(self, exploreIter):
        """ Sets the time stamp of all classifiers in the set to the current time. The current time
        is the number of exploration steps executed so far.  """
        for i in range(len(self.action_set)):
            ref = self.action_set[i]
            self.pop_set[ref].updateTimeStamp(exploreIter)

    #def setPredictionArray(self,newPredictionArray):
    #    predictionArray = newPredictionArray

    def getFitnessSum(self, setList):
        """ Returns the sum of the fitnesses of all classifiers in the set. """
        sumCl=0.0
        for i in range(len(setList)):
            ref = setList[i]
            sumCl += self.pop_set[ref].fitness
        return sumCl


    def getPopFitnessSum(self):
        """ Returns the sum of the fitnesses of all classifiers in the set. """
        sumCl = 0.0
        for cl in self.pop_set:
            sumCl += cl.fitness
        return sumCl


    def getIdenticalClassifier(self, newCl):
        """ Looks for an identical classifier in the population. """
        for ref in self.match_set:
            if newCl.equals(self.pop_set[ref]):
                return self.pop_set[ref]
        return None


    def clearSets(self):
        """ Clears out references in the match and action sets for the next learning iteration. """
        self.match_set = []
        self.action_set = []

    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # EVALUTATION METHODS
    #--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def runPopAveEval(self, exploreIter):
        """ Calculates some summary evaluations across the rule population including average generality. """
        genSum = 0
        #agedCount = 0
        for cl in self.pop_set:
            genSum += (cons.env.format_data.numb_attributes - len(cl.condition)) * cl.numerosity
        if self.micro_size == 0:
            self.mean_generality = 'NA'
        else:
            self.mean_generality = genSum / float(self.micro_size * cons.env.format_data.numb_attributes)

        #-------------------------------------------------------
        # CONTINUOUS PHENOTYPE
        #-------------------------------------------------------
        if not cons.env.format_data.discrete_action:
            sumRuleRange = 0
            for cl in self.pop_set:
                sumRuleRange += (cl.phenotype[1] - cl.phenotype[0])*cl.numerosity
            phenotypeRange = cons.env.format_data.action_list[1] - cons.env.format_data.action_list[0]
            self.ave_phenotype_range = (sumRuleRange / float(self.micro_size)) / float(phenotypeRange)


    def runAttGeneralitySum(self, isEvaluationSummary):
        """ Determine the population-wide frequency of attribute specification, and accuracy weighted specification.  Used in complete rule population evaluations. """
        if isEvaluationSummary:
            self.attribute_spec_list = []
            self.attribute_acc_list = []
            for i in range(cons.env.format_data.numb_attributes):
                self.attribute_spec_list.append(0)
                self.attribute_acc_list.append(0.0)
            for cl in self.pop_set:
                for ref in cl.specifiedAttList: #for each attRef
                    self.attribute_spec_list[ref] += cl.numerosity
                    self.attribute_acc_list[ref] += cl.numerosity * cl.accuracy


    def getPopTrack(self, accuracy, exploreIter, trackingFrequency):
        """ Returns a formated output string to be printed to the Learn Track output file. """
        trackString = str(exploreIter)+ "\t" + str(len(self.pop_set)) + "\t" + str(self.micro_size) + "\t" + str(accuracy) + "\t" + str(self.mean_generality)  + "\t" + str(cons.timer.returnGlobalTimer())+ "\n"
        if cons.env.format_data.discrete_action: #discrete phenotype
            print(("Epoch: "+str(int(exploreIter/trackingFrequency))+"\t Iteration: " + str(exploreIter) + "\t MacroPop: " + str(len(self.pop_set))+ "\t MicroPop: " + str(self.micro_size) + "\t AccEstimate: " + str(accuracy) + "\t AveGen: " + str(self.mean_generality)  + "\t Time: " + str(cons.timer.returnGlobalTimer())))
        else: # continuous phenotype
            print(("Epoch: "+str(int(exploreIter/trackingFrequency))+"\t Iteration: " + str(exploreIter) + "\t MacroPop: " + str(len(self.pop_set))+ "\t MicroPop: " + str(self.micro_size) + "\t AccEstimate: " + str(accuracy) + "\t AveGen: " + str(self.mean_generality) + "\t PhenRange: " +str(self.ave_phenotype_range) + "\t Time: " + str(cons.timer.returnGlobalTimer())))

        return trackString


    def parallelMatching( self, i ): #( ( indices, condition, state, id ) ):
        """ used when multiprocessing is enabled. """
        if self.pop_set[ i ].match( self.current_instance ):
            return i
        return None
