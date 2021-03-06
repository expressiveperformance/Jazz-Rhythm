from jazzr.rhythm.parsers import *
from jazzr.models import *
from jazzr.tools import commandline
import random, pickle, datetime, os

ONSET = 0
TIE = 1

def load():
    files = sorted(os.listdir('results'))
    choice = commandline.menu('Choose', files)
    if choice != -1:
        f = open('results/{0}'.format(files[choice]), 'rb')
        return pickle.load(f)

def evaluate(nfolds=10, n=15, length=20, noise=False, flatPrior=None, p=None, save=True, collection='explicitswing', noAllowed=False):
    corpus = annotations.corpus(collection=collection)
    folds = getFolds(corpus, folds=nfolds)
    results = []
    i = 1
    allowed = treeconstraints.train(corpus)
    if noAllowed:
        allowed = None
    for trainset, testset in folds:
        print 'Fold {0}'.format(i)
        i += 1

        # Train a parser
        expressionModel = expression.train(trainset)
        rhythmModel = pcfg.train(trainset)
        if noise:
            expressionModel=expression.additive_noise(0.1)
        if flatPrior:
            rhythmModel = pcfg.flat_prior(p=p)
            #rhythmModel = pcfg.flat_prior(p=1.0)
        parser = StochasticParser(trainset, n=n, expressionModel=expressionModel, rhythmModel=rhythmModel)
        parser.allowed = allowed
        # Get the first few bars from a piece
        tests, labels = getTests(testset, n=length)
        annot = [x[0] for x in testset]
        for test, label, annotation in zip(tests, labels, annot):
            print annotation.name
            if len(test) <= 2:
                print 'Skipping too short test'
                continue
            parses = parser.parse_onsets(test)
            if len(parses) > 0:
                results.append((parses[0], label, annotation))
                precision, recall = measure(results[-1:])
                print 'Precision {0} recall {1}.'.format(precision, recall)
                precision, recall = measure(results)
                print 'Averages: precision {0} recall {1}.'.format(precision, recall)

    time = str(datetime.datetime.now())
    exp = 'expression'
    prior = 'pcfg'
    if noise:
        exp = 'noise'
    if flatPrior:
        prior = 'flat'
        if p != None:
            prior = 'flat_p={0}'.format(p)
    extra = ''
    if noAllowed:
        extra = '_maxdepth'
    if save:
        f = open('results/{0}_expression={4}_prior={5}_length={1}_n={2}_folds={3}{6}'.format(time, length, n, nfolds, exp, prior, extra), 'wb')
        pickle.dump(results, f)
    return results

def measure(results):
    recallScore = 0
    precisionScore = 0
    nRecall = 0
    nPrecision = 0

    for i in range(len(results)):
        parse, label = parseAndLabel(results, i)
        score, n = rank(claims(parse), claims(label))
        p1 = (score/float(n), score, n)
        score, n = rank(claims(parse, [(2, 0)]), claims(label))
        p2 = (score/float(n), score, n)
        score, n = rank(claims(parse), claims(label, [(2, 0)]))
        p3 = (score/float(n), score, n)
        precisionScore += max([p1, p2, p3], key=lambda x:x[0])[1]
        nPrecision += max([p1, p2, p3], key=lambda x:x[0])[2]

        score, n = rank(claims(label), claims(parse))
        r1 = (score/float(n), score, n)
        score, n = rank(claims(label, [(2, 0)]), claims(parse))
        r2 = (score/float(n), score, n)
        score, n = rank(claims(label), claims(parse, [(2, 0)]))
        r3 = (score/float(n), score, n)
    #  n, score = getRecallScore(parse, label)
        recallScore += max([r1, r2, r3], key=lambda x:x[0])[1]
        nRecall += max([r1, r2, r3], key=lambda x:x[0])[2]
    return precisionScore/float(nPrecision), recallScore/float(nRecall)

def precision(parse, label):
    tp, fp, tnl, fn = downbeat_detection(parse, label)
    precision = 0
    if tp + fp != 0:
        precision = tp/float(tp + fp)
    return precision

def recall(parse, label):
    tp, fp, tn, fn = downbeat_detection(parse, label)
    recall = 0
    if tp + fn != 0:
        recall = tp/float(tp + fn)
    return recall

def f_measure(results):
    p, r = measure(results)
    return 2*(p*r)/float(p+r)

def getTests(testset, n=20):
    tests = []
    labels = []
    for test, parse in testset:
        #onsets = getNBars(test, measures)
        label = getNNotes(parse, n)
        onsets = getOnsets(parse, performance=True)[:len(getOnsets(label))+1]
        tests.append(onsets)
        labels.append(label)
    return tests, labels

def getNBars(annot, measures):
    onsets = []
    bar = None
    for i in range(len(annot)):
        if annot.type(i) in [Annotation.NOTE, Annotation.END, Annotation.SWUNG]:
            if bar == None:
                bar = annot.bar(annot.position(i))
            else:
                if annot.bar(annot.position(i)) >= bar + measures:
                    break
            onsets.append(annot.perf_onset(i))
    return onsets

def getNNotes(S, n):
    if not S.isSymbol():
        return None
    if abs(len(getOnsets(S.children[0])) - n) < \
        abs(len(getOnsets(S)) - n):
        return getNNotes(S.children[0], n)
    else:
        return S


def symbol_to_list(S, level=0, beat=0, ties=False, division=[1]):
    treelist = []
    if S.isSymbol():
        for child, beat in zip(S.children, range(len(S.children))):
            treelist += symbol_to_list(child, level=level+1, beat=beat, ties=ties, division=division+[len(S.children)])
    elif S.isOnset():
        treelist.append((ONSET, beat, level, division))
    elif S.isTie() and ties:
        treelist.append((TIE, beat, level, division))
    return treelist

def claims(S, D=[], verbose=False):
    c = []
    if S.isSymbol():
        d = len(S.children)
        for i in range(d):
            c += claims(S.children[i], D=D + [(d, i)])
    if S.isOnset():
#    timesig = [d[0] for d in D]
        onsetclaims = []
        for i in range(len(D)):
            onsetclaims.append(D[i])
#    for i in range(len(timesig), 0, -1):
#      onsetclaims.append((timesig[0:i], D[i-1][1]))
        c.append(tuple(onsetclaims))
    return c

def rank(claims, claims_star, verbose=False):
    R = 0
    N = 0
    counted = []
    for c, c_star in zip(claims, claims_star):
        for i in range(len(c)):
            if c[0:i+1] in counted: continue
            N += 1
            counted.append(c[0:i+1])
            if i < len(c_star):
                if c[i] == c_star[i]:
                    R += 1
    return R, N

def getFolds(corpus, folds=5):
    n = len(corpus)
    results = []
    for i in range(folds):
        trainset = []
        testset = []
        n_test = int(n/float(folds))
        for j in range(n_test):
            index = int(random.random() * (n-j))
            testset += [corpus[index]]
            del corpus[index]
        trainset = corpus
        results.append((trainset, testset))
        corpus = trainset + testset
    return results

def parseAndLabel(results, i):
    p = results[i][0]
    notes = getOnsets(p)
    return p, getSubTree(notes, results[i][1])

def compare(results, i, scale=False):
    p, l = parseAndLabel(results, i)
    latex.view_symbols([p, l], scale=scale)

def getSubTree(notes, parse):
    if parse.isSymbol():
        childContains = False
        for child in parse.children:
            if contains(notes, getOnsets(child, performance=True)):
                childContains = True
                res = getSubTree(notes, child)
                if res != None:
                    return res
            if not childContains:
                return parse
    return None

def getOnsets(S, performance=False):
    notes = []
    if S.isSymbol():
        for child in S.children:
            notes += getOnsets(child, performance=performance)
    elif S.isOnset():
        if performance:
            return [S.annotation.perf_onset(S.index)]
        else:
            return [S.on]
    return notes

def getPitches(S):
    notes = []
    if S.isSymbol():
        for child in S.children:
            notes += getPitches(child)
    elif S.isOnset():
        return [S.annotation.pitch(S.index)]
    return notes

def contains(small, big):
    for i in xrange(len(big)-len(small)+1):
        for j in xrange(len(small)):
            if big[i+j] != small[j]:
                break
            else:
                return i, i+len(small)
    return False

def downbeat_detection(parse, correctparse):
    results = symbol_to_list(parse)
    labels = symbol_to_list(correctparse)
    n = 0
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    #for i in range(len(results)):
    #  print results[i], labels[i]
    for i in range(len(results)):
        type, beat, level, division = results[i]
        ltype, lbeat, llevel, division = labels[i]
        if type == ONSET and beat == 0:
            if beat == lbeat:
                tp += 1
            else:
                fp += 1
        elif type == ONSET:
            if lbeat != 0:
                tn += 1
            else:
                fn += 1
    precision = recall = 0
    if tp + fp != 0:
        precision = tp/float(tp + fp)
    if tp + fn != 0:
        recall = tp/float(tp + fn)
    return tp, fp, tn, fn

def getPrecisionScore(parse, label, a_perf=False, b_perf=True, verbose=False):
    if verbose:
        if label == None:
            label = Tie()
        latex.view_symbols([parse, label], scale=False)
    score = 0
    n = 0
    # If this is a symbol than this symbol is one fact claimed by the parse
    # it's correct if the onsets each of its children governs is the same as for the parse
    division = len(parse.children)
    i = 0
    while i < division:
        n += 1
        if label == None:
            if parse.children[i].isSymbol():
                newN, newScore = getPrecisionScore(parse.children[i], None, a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                n += newN
                score += newScore
            i += 1
            continue
        if label.children == None:
            if parse.children[i].isSymbol():
                newN, newScore = getPrecisionScore(parse.children[i], None, a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                n += newN
                score += newScore
            i += 1
            continue
        if i >= len(label.children):
            if parse.children[i].isSymbol():
                newN, newScore = getPrecisionScore(parse.children[i], None, a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                n += newN
                score += newScore
            i += 1
            continue
        # Parse claims a division into x and y, see if label does so too
        if getOnsets(parse.children[i], performance=a_perf) == getOnsets(label.children[i], performance=b_perf):
            score += 1
            if parse.children[i].isSymbol():
                newN, newScore = getPrecisionScore(parse.children[i], label.children[i], a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                n += newN
                score += newScore
        else:
            # Only do this at top level?
            #if contains(getOnsets(label, performance=b_perf), getOnsets(parse.children[i], performance=a_perf)):
            #  if parse.children[i].isSymbol():
            #    newN, newScore = getPrecisionScore(parse.children[i], label, a_perf=a_perf, b_perf=b_perf, verbose=verbose)
            #    n += newN
            #    score += newScore
            if contains(getOnsets(label.children[i], performance=b_perf), getOnsets(parse.children[i], performance=a_perf)):
                if parse.children[i].isSymbol():
                    newN, newScore = getPrecisionScore(parse.children[i], label.children[i], a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                    n += newN
                    score += newScore
            else:
                if parse.children[i].isSymbol():
                    newN, newScore = getPrecisionScore(parse.children[i], None, a_perf=a_perf, b_perf=b_perf, verbose=verbose)
                    n += newN
                    score += newScore
        i += 1
    return n, score

def getRecallScore(parse, label, verbose=False):
    return getPrecisionScore(label, parse, a_perf=True, b_perf=False, verbose=verbose)


from jazzr.rhythm.symbol import *
on = Onset(0, 0, 0)
s = Symbol.fromSymbols([on, on])
t = Symbol.fromSymbols([Tie(), on])
v = Symbol.fromSymbols([on, Tie()])
A = Symbol.fromSymbols([s, s])
B = Symbol.fromSymbols([s, Symbol.fromSymbols([t, on])])
C = Symbol.fromSymbols([Symbol.fromSymbols([t, s]), Symbol.fromSymbols([v, Tie()])])
a = Symbol.fromSymbols([Tie(), s])
b = Symbol.fromSymbols([s, Tie()])
D = Symbol.fromSymbols([a, b])
