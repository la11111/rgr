#!/usr/bin/env python

import random
from rgr import *
import string
import sys

def make_random_kwargs():
    kwargs = {}
    for i in range(random.randint(1,10)):
        key = []
        value = []
        key.append(random.choice(string.letters))
        for k in range(random.randint(2,16)):
            #key.append(random.choice(string.letters))
            key.append(random.choice(string.letters+"_0123456789"))
        for v in range(random.randint(5,20)):
            #value.append(random.choice(string.letters))
            value.append(random.choice(string.letters+"_:' 0123456789"))
        kwargs[''.join(key)] = ''.join(value)
    return kwargs

def dump_everything():
    print '===================='
    print 
    print "nodes:", g.nodes
    print "edges:", g.edges
    print "leftovers:"
    for k in g.rc.keys(): print k
    print 
    print '===================='
    for node in g.nodes:
        n = Node(g,node) 
        print "---"
        print 'id', n._id
        print 'pn:'
        for k in n._pn:
            print '\t', k, n._pn[k]
        print 'cn:'
        for k in n._cn:
            print '\t', k, n._cn[k]
        print 'oe', n._oe
        print 'ie', n._ie
        print 'properties:'
        for p in n._properties:
            print '\t', p, n._properties[p]

    print "*******"
    for edge in g.edges:
        e = Edge(g,edge)
        print "---"
        print 'id', e._id
        print 'in', e._in
        print 'on', e._on
        print 'properties:'
        for p in e._properties:
            print '\t', p, e._properties[p]


nodes_to_create = 50
edges_to_create = 100

ri = random.randint

g = Graph()

for k in g.rc.keys(): g.rc.delete(k)

g = Graph()

for i in range(nodes_to_create):
    g.addn(**make_random_kwargs())

for i in range(edges_to_create):
    g.adde(ri(0, nodes_to_create-1),ri(0, nodes_to_create-1),**make_random_kwargs()) 

#dump_everything()
n1 = Node(g,25)
e1 = Edge(g,50)

for node_obj in n1._pn():
    print node_obj._id
    print node_obj._p

for edge_obj in n1._ie():
    print edge_obj._id
    print edge_obj._p

print e1._in()


for n in g.nodes:
    try:
        g.deln(n)
    except:
        print "ERROR: {}".format(n)
        next

dump_everything()
