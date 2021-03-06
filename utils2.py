#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 28 15:13:55 2020

@author: fan
"""

#%%
import numpy as np
from numpy.linalg import inv
from numpy.random import choice
from scipy.special import logit, expit
from scipy.stats import multivariate_normal, norm, truncnorm
from scipy.stats import wishart#, invwishart
from scipy.stats import dirichlet
from sklearn.cluster import KMeans

#import pandas as pd
from copy import copy

#%%

# 1-d Gaussian stuff (score model)

## linked score

def initializeLinkedScore(L, initThres = 0.6):
    '''
    Initialize things based on thresholding on the linked score;
    Returns:
        - logit transformed link score
        - indices of pairs that are selected in the point processes
        - initial value of muL, gammaL (inverse of sigma^2_l)
    L: length N linked scores of all pairs
    '''
    
    inds = np.where(L > initThres)[0]
    
    L = logit(L)
    Thres = logit(initThres)
    
    muL = np.mean(L[L > Thres])
    
    deMean = np.where(L > Thres, L - muL, L)
    
    gammaL = 1/np.mean(deMean ** 2)
    
    return L, inds, muL, gammaL


def updateLModel(L, indsMF, indsFM, muL, gammaL, gammaPrior):
    '''
    Update linked score model (muL and gammaL) given the point configurations
    Returns muL and gammaL
    L: length N linked scores (transformed) of all pairs
    indsMF: indices of points in the MF process
    indsFM: indices of points in the FM process
    gammaPrior: a dictionary of prior for gammaL, "nu0" and "sigma0"
    '''
    
    inds = list(indsMF) + list(indsFM)
    
    mu_mean = np.mean(L[inds])
    mu_std = 1/np.math.sqrt(len(inds) * gammaL)
    
    muL = truncnorm(a=(0-mu_mean)/mu_std, b=np.inf).rvs() * mu_std + mu_mean
    
    #deMean = L
    deMean = copy(L)
    deMean[inds] = deMean[inds] - muL
    SS = np.sum(deMean ** 2)
    
    gammaL = np.random.gamma((gammaPrior['nu0'] + len(L))/2, 
                             2/(gammaPrior['nu0'] * gammaPrior['sigma0'] + SS))
    
    return muL, gammaL

def evalLLikelihood(L, indsMF, indsFM, muL, gammaL, subset=None, log=True):
    '''
    Evaluate the linked score component of the likelihood (on a subset of entries);
    Returns length len(L) (or len(subset)) array of (log-)likelihood
    L: length N linked scores (transformed) of all pairs
    indsMF: indices of points in the MF process
    indsFM: indices of points in the FM process
    muL, gammaL: parameters of the L model
    subset: list of SORTED indices (if None, then evaluate likelihood on all entries)
    log: bool, output log-likelihood?
    '''
    # get the indices in either point process
    #inds= list(E_MF.keys()) + list(E_FM.keys())
    inds = list(indsMF) + list(indsFM)
    
    if subset is not None:
        indsIn = list(set(subset) & set(inds))
        indsOut = list(set(subset) - set(inds))
        res = np.empty(len(subset))
        indices = np.array(subset)
    else:
        indices = np.arange(len(L))
        indsIn = inds
        indsOut = list(set(indices) - set(inds))
        res = np.empty(len(L))
        
    sd = 1/np.math.sqrt(gammaL)  
    #logDensIn = norm(loc=muL, scale=sd).logpdf(L[indsIn]) if len(indsIn) > 0 else 
    if len(indsIn) > 0:
        logDensIn = norm(loc=muL, scale=sd).logpdf(L[indsIn])
        res[np.searchsorted(indices, indsIn)] = logDensIn
    if len(indsOut) > 0:
        logDensOut = norm(loc=0, scale=sd).logpdf(L[indsOut])
        res[np.searchsorted(indices, indsOut)] = logDensOut
        
    if not log:
        res = np.exp(res)
        
    return res
        

## direction score
    
def initializeDirectScore(D, inds):
    '''
    Initialize direction score stuff based on thresholding results of linked score;
    Returns:
        - logit transformed direction score
        - indices of pairs that are selected in each point process
        - initial value of muNegD, muD, gammaD (inverse of sigma^2_d)
    D: length N linked scores of all pairs (in same order as L)
    '''
    
    D = logit(D)
    
    inds = set(inds)
    indsMF = inds & set(np.where(D > 0)[0])
    indsFM = inds - indsMF
    
    indsMF = list(indsMF)
    indsFM = list(indsFM)
    
    muD = np.mean(D[indsMF])
    muNegD = np.mean(D[indsFM])
    
    Dsel = D[list(inds)]
    deMean = np.where(Dsel > 0, Dsel-muD, Dsel-muNegD)
    gammaD = 1/np.mean(deMean ** 2)
    
    return D, indsMF, indsFM, muD, muNegD, gammaD


def updateDModel(D, indsMF, indsFM, muD, muNegD, gammaD, gammaPrior):
    '''
    Update linked score model (muL and gammaL) given the point configurations
    Returns muD, muNegD, gammaD
    D: length N MF-direction scores (transformed) of all pairs
    indsMF: indices of points in the MF process
    indsFM: indices of points in the FM process
    gammaPrior: a dictionary of prior for gammaL, "nu0" and "sigma0"
    '''
    
    indsMF = list(indsMF) 
    indsFM = list(indsFM)
    
    muD_mean = np.mean(D[indsMF])
    muD_std = 1/np.math.sqrt(len(indsMF) * gammaD)
    muD = truncnorm(a=(0-muD_mean)/muD_std, b=np.inf).rvs() * muD_std + muD_mean
    
    muNegD_mean = np.mean(D[indsFM])
    muNegD_std = 1/np.math.sqrt(len(indsFM) * gammaD)
    muNegD = truncnorm(a=-np.inf, b=(0-muNegD_mean)/muNegD_std).rvs() * muNegD_std + muNegD_mean
    
    #deMean = D
    deMean = copy(D)
    deMean[indsMF] = deMean[indsMF] - muD
    deMean[indsFM] = deMean[indsFM] - muNegD
    SS = np.sum(deMean ** 2)
    
    gammaD = np.random.gamma((gammaPrior['nu0'] + len(D))/2, 
                             2/(gammaPrior['nu0'] * gammaPrior['sigma0'] + SS))
    
    return muD, muNegD, gammaD


def evalDLikelihood(D, indsMF, indsFM, muD, muNegD, gammaD, subset=None, log=True):
    '''
    Evaluate the direction score component of the likelihood (on a subset of entries);
    Returns length len(D) (or len(subset)) array of (log-)likelihood
    D: length N direction scores (transformed) of all pairs
    indsMF: indices of points in the MF process
    indsFM: indices of points in the FM process
    muD, muNegD, gammaD: parameters of the D model
    subset: list of SORTED indices (if None, then evaluate likelihood on all entries)
    log: bool, output log-likelihood?
    '''
    # get the indices in each point process
    indsMF = list(indsMF) 
    indsFM = list(indsFM)
    
    # get indices in MF, MF and out
    if subset is not None:
        indsMF = list(set(subset) & set(indsMF))
        indsFM = list(set(subset) & set(indsFM))
        indsOut = list(set(subset) - (set(indsMF) | set(indsFM)))
        res = np.empty(len(subset))
        indices = np.array(subset)
    else:
        indices = np.arange(len(D))
        indsOut = list(set(indices) - (set(indsMF) | set(indsFM)))
        res = np.empty(len(D))
        
    sd = 1/np.math.sqrt(gammaD)  

    if len(indsMF) > 0:
        logDensMF = norm(loc=muD, scale=sd).logpdf(D[indsMF])
        res[np.searchsorted(indices, indsMF)] = logDensMF
    if len(indsFM) > 0:
        logDensFM = norm(loc=muNegD, scale=sd).logpdf(D[indsFM])
        res[np.searchsorted(indices, indsFM)] = logDensFM
    if len(indsOut) > 0:
        logDensOut = norm(loc=0, scale=sd).logpdf(D[indsOut])
        res[np.searchsorted(indices, indsOut)] = logDensOut
        
    if not log:
        res = np.exp(res)
        
    return res

#%%
   
# test score model update
    
if __name__ == '__main__':
#    ## test initialization
#    L = (1-0.3)* np.random.random_sample(100) + 0.3
#    D = np.random.random_sample(100)
#    
#    Ltrans, inds, muL, gammaL = initializeLinkedScore(L, initThres = 0.6)
#    Dtrans, indsMF, indsFM, muD, muNegD, gammaD = initializeDirectScore(D, inds)
#        
#    ## test update
#    gaPrior = {'nu0': 2, 'sigma0': 1}
#    ## completely made up points...
#    E_MF = dict(zip(indsMF, np.random.random_sample(len(indsMF))))
#    E_FM = dict(zip(indsFM, np.random.random_sample(len(indsFM))))
#    
#    print(updateLModel(Ltrans, E_MF, E_FM, muL, gammaL, gaPrior))
#    print(updateDModel(Dtrans, E_MF, E_FM, muD, muNegD, gammaD, gaPrior))
    
    Ltrans, inds, muL, gammaL = initializeLinkedScore(L, initThres = 0.6)
    Dtrans, indsMF, indsFM, muD, muNegD, gammaD = initializeDirectScore(D, inds)
    
    print(Ltrans)
    print(Dtrans)
    
    E_MF = {i:v for i,v in E.items() if i in range(50)}
    E_FM = {i:v for i,v in E.items() if i in range(50,100)}
    
    gaPrior = {'nu0': 2, 'sigma0': 1}
    
    maxIter = 1000
    
    params = {'muL': [], 'gammaL':[], 'muD': [], 'muNegD': [], 'gammaD': []}
    
    for it in range(maxIter):
        muL, gammaL = updateLModel(Ltrans, E_MF, E_FM, muL, gammaL, gaPrior)
        params['muL'].append(muL); params['gammaL'].append(gammaL)
        
        muD, muNegD, gammaD = updateDModel(Dtrans, E_MF, E_FM, muD, muNegD, gammaD, gaPrior)
        params['muD'].append(muD); params['muNegD'].append(muNegD)
        params['gammaD'].append(gammaD)

    print(Ltrans)
    print(Dtrans)

#%%

# The point process stuff

# =============================================================================
# def initializePP(E, indsMF, indsFM):
#     '''
#     Initialize MF and FM point process configurations.
#     Returns:
#         #- E_MF, E_FM, E_0: dictionary of (a_M, a_F) points on each type of surface
#         - gamma: the scale for the entire process
#         - probs: the length-3 vector of type probabilities/proportions
#     E: dictionary of all (a_M, a_F) points (for all the pairs in data)
#     indsMF, indsFM: some assignment of indices in MF and FM surfaces
#     '''
#     
# #    E_MF = {pair: age for pair, age in E.items() if pair in indsMF}
# #    E_FM = {pair: age for pair, age in E.items() if pair in indsFM}
# #    E_0 = {pair: age for pair, age in E.items() if (pair not in indsFM and pair not in indsMF)}
#     
#     gamma = len(E)
#     
#     probs = [len(E) - len(indsMF) - len(indsFM) ,len(indsMF), len(indsFM)]
#     probs = np.array(probs)/gamma
#     
#     return gamma, probs
# =============================================================================


def updateGamma(C, gammaPrior):
    '''
    Update gammaMF and gammaFM based on C indicators
    - C: values in 0,1,2,3
    - gammaPrior: dictionary of prior
    
    '''
    N = len(C)
    N_MF = np.sum(C%2==0)
    N_FM = N - N_MF
    
    gammaMF = np.random.gamma(gammaPrior['n0']+N_MF, 1/(gammaPrior['b0']+1))
    gammaFM = np.random.gamma(gammaPrior['n0']+N_FM, 1/(gammaPrior['b0']+1))
    
    return gammaMF, gammaFM


def updateEta(C, etaPrior):
    '''
    Update thinning prob eta+ and eta- on MF, FM surfaces
    - C: values in 0,1,2,3
    - etaPrior: dictionary of prior for eta
    
    '''
    
    etaMF = np.random.beta(etaPrior['a']+np.sum(C==2), etaPrior['b']+np.sum(C==0))
    etaFM = np.random.beta(etaPrior['a']+np.sum(C==3), etaPrior['b']+np.sum(C==1))
    
    return etaMF, etaFM


def getPoints(E, subset=None, flip = False):
    '''
    Return a (n,2) array of the points in event set E (or a subset)
    E: dictionary of indice, age pair
    subset: list of subset indices
    flip: boolean - flip the two columns? (used for FM surface)
    
    #(UPDATE: return None instead of raising error when E is empty)
    '''
    if not E:
        # if E is empty, raise an Error
        raise ValueError('The point event set is empty!')
        #X = None
    else:
        #p = X.shape[1]
        if subset:
            E_sub = {i: age for i,age in E.items() if i in subset}
            X = np.array(list(E_sub.values()))
            #n = len(subset)
        else:
            X = np.array(list(E.values()))
            #n = len(E)
        #X = X.reshape((n,p))
        
        if flip:
            X = X[:,(1,0)]

    return X

#%%
if __name__ == '__main__':
    E = {i: (np.random.random_sample(),np.random.random_sample()) for i in range(100)}
    X = getPoints(E)
    print(X.shape)
    
    inds1 = choice(range(100), size=38, replace=False)
    inds2 = choice(list(set(range(100)) - set(inds1)), size = 30, replace=False)
    
    E1, E2, gam1, gam2 = initializePP(E, inds1, inds2)
    
    E1, E2, chosen = proposePP(E, E1, E2, 10)

#%%

# Gaussian mixture stuff (spatal density model)

def initializeGMM(X, K=2):
    '''
    Initialize a finite Gaussian mixture model via k-means;
    Returns components (mean and precision matrix) and component labels
    X: (n,p) array of data
    K: number of components
    '''
    kmeans = KMeans(n_clusters=K).fit(X)
    labels = kmeans.labels_
    centers = kmeans.cluster_centers_
    
    components = list()
    for k in range(K):
        components.append((centers[k,:], np.cov(X[labels==k,:],rowvar=False)))
        
    return components, labels


def updateOneComponent(X, mu, precision, muPrior, precisionPrior):
    '''
    X: (n,p) array of data
    mu: (p,1) array of current mean
    precision: (p,p) matrix of current precision
    muPrior: dictionary of prior mean and precision
    precisionPrior: dictionary of prior df and invScale
    '''
    
    n = X.shape[0]
    An_inv = inv(muPrior['precision'] + n * precision)
    Xsum = np.sum(X, axis=0)
    bn = muPrior['precision'].dot(muPrior['mean']) + precision.dot(Xsum)
    
    mu = multivariate_normal(An_inv.dot(bn), An_inv).rvs()
    
    S_mu = np.matmul((X-mu).T, X-mu)
    
    precision = wishart(precisionPrior['df'] + n, 
                        inv(precisionPrior['invScale'] + S_mu)).rvs()
    
    return mu, precision

def updateGaussianComponents(X, Z, components, muPrior, precisionPrior):
    '''
    X: (n,p) array of data
    Z: length n, array like component indicator
    components: list of (mu, precision) for K Gaussian components
    muPrior: dictionary of prior mean and precision
    precisionPrior: dictionary of prior df and invScale
    '''
    K = len(components)
    
    for k in range(K):
        subX = X[Z==k,:]
        if subX.shape[0] > 0:
            mu, precision = components[k]
            components[k] = updateOneComponent(subX, mu, precision, 
                      muPrior, precisionPrior)
            
    return components

def getProbVector(p):
    '''
    carry out a hack correction here:
        if an entry is -inf -> -3000
        if an entry is inf -> 3000
        
    '''
    p[p==np.inf] = 3000
    p[p==-np.inf] = 3000
    
    p = np.exp(p - np.max(p))
    #print(p)
    return p/p.sum()

def updateComponentIndicator(X, weight, components):
    '''
    X: (n,p) array of data
    components: list of (mu, precision) for K Gaussian components
    (05/13 fix: use weights in indicator update! previous version was wrong)
    '''
    K = len(components)
    n = X.shape[0]
    
    logDens = np.empty((K,n))
    
    for k in range(K):
        mu, precision = components[k]
        MVN = multivariate_normal(mu, inv(precision))
        logDens[k,:] = MVN.logpdf(X) + np.log(weight[k])
#        logProb = MVN.logpdf(X)
#        if np.any(np.isnan(logProb)):
#            print(mu, precision)
#            raise ValueError("NaN in log likelihood!")
#        else:
#            logDens[k,:] = logProb
        
    Z = np.apply_along_axis(lambda v: choice(range(K), replace=False, 
                                             p=getProbVector(v)), 0, logDens)
    return Z

def updateMixtureWeight(Z, weightPrior):
    '''
    Z: length n, array like component indicator
    weightPrior: length K, array like prior (for the Dirichlet prior)
    '''
    unique, counts = np.unique(Z, return_counts=True)
    mixtureCounts = dict(zip(unique,counts))
    
    alpha = copy(weightPrior)
    
    for k in mixtureCounts:
        alpha[k] += mixtureCounts[k]
        
    return dirichlet(alpha).rvs()[0]

def evalDensity(X, weight, components, log=True):
    '''
    Evaluate the entire density function (after mixture) on points X;
    Returns a length-n array of density/log-density
    X: (n,p) array of data
    weight: length K vector of mixture weights
    components: list of (mu, precision) for K Gaussian components
    '''
    
    n = X.shape[0]
    K = len(weight)
    
    mix_dens = np.empty((n,K))
    
    for k in range(K):
        mu, precision = components[k]
        MVN = multivariate_normal(mu, inv(precision))
        mix_dens[:,k] = MVN.pdf(X)
        
    #print(mix_dens)
        
    total_dens = np.sum(weight * mix_dens, axis=1)
    
    if log:
        total_dens = np.log(total_dens)
        
    return total_dens
#%% test
#x_test = np.random.randn(50,2) + 2

# initialize function
#components, Z = initializeGMM(x_test)

# update component function
#muP = {'mean': np.array([0,0]), 'precision': np.eye(2)}
#preP = {'df': 2, 'invScale': np.eye(2)*.01}
#
#updateOneComponent(x_test, np.array([0.1,0.1]), np.eye(2), muP, preP)

# update indicator function
#components = [(np.zeros(2), np.eye(2)), (np.ones(2), np.eye(2) * 0.01)]
#Z = updateComponentIndicator(x_test, components)
#Z.shape[0] == x_test.shape[0]

# update mixture weight function
#updateMixtureWeight(Z, np.ones(2))


#%% test out the whole process
if __name__ == "__main__":

    from time import perf_counter
    
    muP = {'mean': np.array([0,0]), 'precision': np.eye(2)}
    preP = {'df': 2, 'invScale': np.eye(2)*.0001}
    weightP = np.ones(2)
    
    x_1 = np.random.randn(100,2) + 10
    x_2 = np.random.randn(100,2) -10
    x_test = np.concatenate((x_1,x_2),axis=0)
    
    tic = perf_counter()
    
    components, Z = initializeGMM(x_test)
    
    maxIter = 100
    
    for i in range(maxIter):
        components = updateGaussianComponents(x_test, Z, components, 
                                              muP, preP)
        Z = updateComponentIndicator(x_test, components)
        w = updateMixtureWeight(Z, weightP)
        
    #log_dens = evalDensity(x_test[:10,:], w, components)
    #print("log likelihood of first 10 points: {:.4f}".format(log_dens))
    
    #print(evalDensity(x_test, w, components))
        
    elapsed = perf_counter() - tic
    
    print("Total time {:.4f} seconds, with {:.4f} seconds per iteration.".format(elapsed,elapsed/maxIter))
        
    # It seems to work...
    # But occassionally would encounter NaN in the log density??
    # Probably fixed...
    
#%%
# re-rest the Gaussian mixture model
#from time import perf_counter
#    
#muP = {'mean': np.array([0,0]), 'precision': np.eye(2)*.0001}
#preP = {'df': 2, 'invScale': np.eye(2)}
#weightP = np.ones(3)
#
#x_test = X[:100,:]
#
#tic = perf_counter()
#
#components, Z = initializeGMM(x_test,K=3)
#
#maxIter = 2000
#
#for i in range(maxIter):
#    components = updateGaussianComponents(x_test, Z, components, 
#                                          muP, preP)
#    Z = updateComponentIndicator(x_test, components)
#    w = updateMixtureWeight(Z, weightP)
#    
##log_dens = evalDensity(x_test[:10,:], w, components)
##print("log likelihood of first 10 points: {:.4f}".format(log_dens))
#
##print(evalDensity(x_test, w, components))
#    
#elapsed = perf_counter() - tic
#
#print("Total time {:.4f} seconds, with {:.4f} seconds per iteration.".format(elapsed,elapsed/maxIter))

#%%
# functions to simulate data
def simulateGMM(N, weight, components):
    comp_counts = np.random.multinomial(N, weight)
    data = None
    for k in range(len(weight)):
        if comp_counts[k] > 0:
            data_k = np.random.multivariate_normal(components[k][0], inv(components[k][1]), comp_counts[k])
            if data is None:
                data = data_k
            else:
                data = np.vstack((data,data_k))
    return data

def simulateLatentPoissonGMM2(Settings):
    '''
    Simulate a dataset with N pairs
    Return: E, L, D
    Settings: a giant dictionary with settings and parameters
        - 'N_MF', 'N_FM': number of points in each point process
        - 'N_MF0', 'N_FM0': number of ghost events in each point process
        - 'muD', 'muNegD', 'muL': the score model means
        - 'gammaD', 'gammaL': the score model precisions (inverse variance)
        - 'componentsMF', 'componentsFM': length K list of GMM components (mean vector, precision matrix)
        - 'weightMF', 'weightFM': mixture weight of GMM on each process
    '''
    
    N_MF = Settings['N_MF']
    N_FM = Settings['N_FM']
    N_MF0 = Settings['N_MF0']
    N_FM0 = Settings['N_FM0']
    
    N = N_MF + N_FM + N_MF0 + N_FM0
    
    #assert N_MF + N_FM <= N
    
    # 1. Generate L and D
    Lin = norm(loc=Settings['muL'], scale = 1/np.sqrt(Settings['gammaL'])).rvs(N_MF + N_FM)
    Lout = norm(loc=0, scale = 1/np.sqrt(Settings['gammaL'])).rvs(N_MF0 + N_FM0)
    L = expit(np.concatenate((Lin, Lout)))
    
    D_MF = norm(loc=Settings['muD'], scale = 1/np.sqrt(Settings['gammaD'])).rvs(N_MF)
    D_FM = norm(loc=Settings['muNegD'], scale = 1/np.sqrt(Settings['gammaD'])).rvs(N_FM)
    D_out = norm(loc=0, scale = 1/np.sqrt(Settings['gammaD'])).rvs(N_MF0 + N_FM0)
    D = expit(np.concatenate((D_MF,D_FM,D_out)))
    
    # 2. Generate E
    ## Those who are in MF
    MFvalues = simulateGMM(N_MF, Settings['weightMF'], Settings['componentsMF'])
    Evalues = list(MFvalues)
    
    ## Those who are in FM
    FMvalues = simulateGMM(N_FM, Settings['weightFM'], Settings['componentsFM'])
    FMvalues = FMvalues[:,::-1] # flip the age, so that it's always (a_M, a_F)
    Evalues.extend(list(FMvalues))

    ## Those who are outside
    ### MF ghost events
    MF0values = simulateGMM(N_MF0, Settings['weightMF'], Settings['componentsMF'])
    Evalues.extend(list(MF0values))
    ### FM ghost events
    FM0values = simulateGMM(N_FM0, Settings['weightFM'], Settings['componentsFM'])
    FM0values = FM0values[:,::-1] # flip the age, so that it's always (a_M, a_F)
    Evalues.extend(list(FM0values))
    
    ## put together
    E = dict(zip(range(N),Evalues))
    
    return E, L, D
    