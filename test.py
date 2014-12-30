#!/usr/bin/env python

import random
from rgr import Graph
import string
import sys

def make_random_kwargs():
    kwargs = {}
    namevalue = [] 
    for v in range(random.randint(5,20)):
        namevalue.append(random.choice(string.letters+"_:' 0123456789"))
    kwargs['name'] = ''.join(namevalue)
    for i in range(random.randint(3,5)):
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
    print "nodes:", g.nodes()
    print "edges:", g.edges()
    print "leftovers:"
    for k in g.redis.keys(): print k
    print 
    print '===================='
    for n in g.nodes():
        print "---"
        print 'id', n.id
        print 'properties:', n.properties()

    print "*******"
    for e in g.edges():
        print "---"
        print 'id', e.id
        print 'properties:', e.properties()
"""
nodes_to_create = 100000
edges_to_create = 500000

ri = random.randint

g = Graph()

g.redis.flushdb()

g = Graph()

print "creating nodes"
for i in xrange(nodes_to_create):
    g.add_node(**make_random_kwargs())
    sys.stdout.write('.')
    sys.stdout.flush()

print "creating edges"
for i in xrange(edges_to_create):
    g.add_edge(ri(0, nodes_to_create-1),ri(0, nodes_to_create-1),**make_random_kwargs()) 
    sys.stdout.write('.')
    sys.stdout.flush()

#dump_everything()
print "testing search"
for n in g.find_nodes(name="jo"):
    print n.properties()
    print
"""
#dump_everything()
g = Graph()
print 'deleting all nodes:'
for n in g.nodes():
    g.del_node(n)
    sys.stdout.write('.')
    sys.stdout.flush()
