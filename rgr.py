#!/usr/bin/env python
""" rgr.py - a(nother) graph database built on Redis """

import sys
import re
from redis import StrictRedis as Redis

#TODO: make everything atomic

class Graph(object):
    """Main interface for adding/removing/looking up
        graph elements.
        
        basic usage:
        you'll add and remove elements via:
        -add_node()/add_edge()
        -del_node()/del_edge()
        
        you can also look up nodes by property:
        get_nodes()/get_edges()

        you can query by property with regex:
        find_nodes()/find_edges()

        all of these methods will return a list of 
        Node() or Edge() objects. From these, you are
        able to look at incoming or ourgoing edges, 
        parent and child nodes, and individually access
        and modify their properties.
    """
    #TODO: better errors
    def __init__(self, name='rgr'):
        """init.
            parameters:
            - name, default:'rgr', 
            the namespace for your graph within redis.
        """
        self.redis = Redis()
        self.name = name
        self.next_nid_key = self.name + ':next_nid' #scalar
        self.next_eid_key = self.name + ':next_eid' #scalar
        self.nodes_key = self.name + ':nodes'       #set
        self.edges_key = self.name + ':edges'       #set
        if not self.redis.exists(self.next_nid_key):
            self.redis.set(self.next_nid_key, 0)
        if not self.redis.exists(self.next_eid_key):
            self.redis.set(self.next_eid_key, 0)

    def add_node(self, **kwargs):
        """Add a node to the graph.
            parameters:
            **kwargs:
                properties that you want to assign to
                the node when you create it.

            i.e.:
            g = rgr.Graph()
            n = g.add_node() #blank node
            n2 = g.add_node(name='john', type='person')
        """
        new_nid = self.redis.get(self.next_nid_key)
        new_node = Node(self, new_nid)
        self.redis.sadd(self.nodes_key, new_nid)
        for k in kwargs:
            new_node.p.__setattr__(k, kwargs[k])
            self._index(new_node.name, k, kwargs[k]) 
        self.redis.incr(self.next_nid_key)
        return new_node

    def add_edge(self, parent, child, **kwargs):
        """Add an edge between two nodes.
        i.e.:

        n = g.add_node(name='john')
        n2 = g.add_node(name='mary')
        e = g.add_edge(n, n2, rel='friends', weight=20)
        """
        new_eid = self.redis.get(self.next_eid_key)
        new_edge = Edge(self, new_eid) 
        self.redis.sadd(self.edges_key, new_eid) 
        for k in kwargs:
            new_edge.p.__setattr__(k, kwargs[k])
            self._index(new_edge.name, k, kwargs[k]) 
        if type(parent) is Node:
            parent = parent.id
        else:
            parent = str(parent)
        if type(child) is Node:
            child = child.id
        else:
            child = str(child)
        if not self.redis.sismember(self.nodes_key, parent):
            raise ValueError(parent)
        if not self.redis.sismember(self.nodes_key, child):
            raise ValueError(child)
        self.redis.set('{}:e:{}:in'.format(self.name, new_eid), parent)
        self.redis.set('{}:e:{}:on'.format(self.name, new_eid), child)
        self.redis.sadd('{}:n:{}:oe'.format(self.name, parent), new_eid)
        self.redis.sadd('{}:n:{}:ie'.format(self.name, child), new_eid)
        #parents / children: zset (sorted set)
        #   where: weight is number of children.
        #   zincrby() will add a member with weight 1 to set if it doesn't exist,
        #       and will increment the currently existing value if it does.
        # zincrby(name, value, amount=1)
        self.redis.zincrby('{}:n:{}:cn'.format(self.name, parent), child)
        self.redis.zincrby('{}:n:{}:pn'.format(self.name, child), parent)
        self.redis.incr(self.next_eid_key)
        return new_edge

    def del_node(self, node):
        """Delete a node from the graph.
        Adjacent edges are also deleted.
        n = g.add_node()
        g.del_node(n) #with Node() object
        g.del_node(254) #by node id
        """
        if type(node) is Node:
            node_obj = node
            node = node.id
        else:
            node = str(node)
            node_obj = Node(self, node)
        if not self.redis.sismember(self.nodes_key, node):
            raise ValueError(node)
        in_edges = self.redis.smembers('{}:n:{}:ie'.format(self.name, node))
        out_edges = self.redis.smembers('{}:n:{}:oe'.format(self.name, node))
        for e in in_edges | out_edges:
            self.del_edge(e)
        props = node_obj.properties()
        for p in props.keys():
            self._deindex(node_obj.name, p, props[p]) 
        self.redis.delete('{}:n:{}:p'.format(self.name, node)) #might be unnecessary
        self.redis.srem(self.nodes_key, node)

    def del_edge(self, edge):
        """Delete an edge from the graph.
        By Edge() object or by edge id.
        """
        if type(edge) is Edge:
            edge_obj = edge
            edge = edge.id
        else:
            edge = str(edge)
            edge_obj = Edge(self, edge)
        if not self.redis.sismember(self.edges_key, edge):
            raise ValueError(edge)
        parent = self.redis.get('{}:e:{}:in'.format(self.name, edge))
        child = self.redis.get('{}:e:{}:on'.format(self.name, edge))
        if self.redis.zincrby('{}:n:{}:cn'.format(self.name, parent), child, -1) == 0:
            self.redis.zrem('{}:n:{}:cn'.format(self.name, parent), child)
        if self.redis.zincrby('{}:n:{}:pn'.format(self.name, child), parent, -1) == 0:
            self.redis.zrem('{}:n:{}:pn'.format(self.name, child), parent)
        self.redis.srem('{}:n:{}:oe'.format(self.name, parent), edge)
        self.redis.srem('{}:n:{}:ie'.format(self.name, child), edge)
        props = edge_obj.properties()
        for p in props.keys(): #most likely works
            self._deindex(edge_obj.name, p, props[p])
        self.redis.delete(
            '{}:e:{}:in'.format(self.name, edge),
            '{}:e:{}:on'.format(self.name, edge),
            '{}:e:{}:p'.format(self.name, edge)
        )
        self.redis.srem(self.edges_key, edge)

    def nodes(self):
        """Return a list of all nodes on the graph. Might be a bad idea if you have
        a million nodes or something."""
        return [Node(self, x) for x in self.redis.smembers(self.nodes_key)]

    def edges(self):
        """Return a list of all edges on the graph. Might be a bad idea if you have
        a million edges or something."""
        return [Edge(self, x) for x in self.redis.smembers(self.edges_key)]

    def get_nodes(self, **kwargs):
        """Return a list of nodes that have properties that exactly match all kwargs supplied.
            i.e.: 
            johns = g.get_nodes(name='John')
            johnsmiths = g.get_nodes(name='John', lastname='Smith')
        """
        return [Node(self, x) for x in self.redis.sinter(['{}:i:n:{}:{}'.format(self.name, k, kwargs[k]) for k in kwargs])]
    
    def get_edges(self, **kwargs):
        """Return a list of edges that have properties that exactly match all kwargs supplied.
            i.e.: 
            haters = g.get_nodes(rel='hates')
        """
        return [Edge(self, x) for x in self.redis.sinter(['{}:i:e:{}:{}'.format(self.name, k, kwargs[k]) for k in kwargs])]

    def find_nodes(self, **kwargs): 
        """Like get_nodes except you can search property *values* by regex.
            i.e.:
            a_to_n = g.find_nodes(lastname=r'^[A-N]')
            for n in a_to_n: print n.p.lastname
        """
        found = []
        for k in kwargs:
            s = set()
            r = re.compile(kwargs[k])
            nodes = self.redis.smembers('{}:i:n:{}'.format(self.name, k))
            for n in nodes:
                if r.search(self.redis.hget('{}:n:{}:p'.format(self.name, n), k)):
                    s.add(n)
            found.append(s)
        return [Node(self, x) for x in set.intersection(*found)]
            
    def find_edges(self, **kwargs): 
        """search for edges by property value using regex.
        """
        found = []
        for k in kwargs:
            s = set()
            r = re.compile(kwargs[k])
            edges = self.redis.smembers('{}:i:e:{}'.format(self.name, k))
            for e in edges:
                if r.search(self.redis.hget('{}:e:{}:p'.format(self.name, e), k)):
                    s.add(e)
            found.append(s)
        return [Edge(self, x) for x in set.intersection(*found)]

    def _index(self, element_name, key, value):
        #TODO type check 
        type, eid = element_name.split(':')[1:]
        self.redis.sadd('{}:i:{}:{}'.format(self.name, type, key), eid)
        self.redis.sadd('{}:i:{}:{}:{}'.format(self.name, type, key, value), eid)

    def _deindex(self, element_name, key, value):
        #TODO type check 
        type, eid = element_name.split(':')[1:]
        self.redis.srem('{}:i:{}:{}'.format(self.name, type, key), eid)
        self.redis.srem('{}:i:{}:{}:{}'.format(self.name, type, key, value), eid)
   

class Node(object):
    """Represents a graph node and provides interface to access
        node properties, as well as adjacent nodes and edges.
        you can create these directly if you have the node id, or else
        any node operations of your Graph() will return sets of these 
        to you.

        parents()/children(): get lists of adjacent nodes 
        in_edges()/out_edges(): get lists of adjacent edges
        properties(): dump a dict of the node's properties

        adding/modifying/deleting properties:

        there's an 'Properties' object in each node called 'p' that provides access 
        to individual properties. you access them like this:

        n = g.add_node()
        n.p.name = 'bob'
        n.p.age = 42
        n.p.blah = 'blah'
        del n.p.blah
        print n.p.age
        
        etc.

        I'd like feedback on this, if possible; would it be better to
        try to do away with this Properties object? I only did it this 
        way to avoid namespace collisions but it could probably be made 
        transparent so that you could just say things like "node.name = 'bob'"
        etc... maybe I'll play with that.

    """
    def __init__(self, graph, id):
        self.graph = graph
        self.id = str(id)
        self.name = graph.name + ':n:' + self.id
        self.p = Properties(self.graph, self.name)
  #TODO fix this so it's more gooder vv and less repeaty 
    def parents(self):
        ret = []
        for n in self._parents():
            ret.append(Node(self.graph, n))
        return ret

    def children(self):
        ret = []
        for n in self._children():
            ret.append(Node(self.graph, n))
        return ret

    def in_edges(self):
        ret = []
        for n in self._in_edges():
            ret.append(Node(self.graph, n))
        return ret

    def out_edges(self):
        ret = []
        for n in self._out_edges():
            ret.append(Node(self.graph, n))
        return ret
 
    def _parents(self):
        return self.graph.redis.zrange('{}:pn'.format(self.name), 0, -1)

    def _children(self):
        return self.graph.redis.zrange('{}:cn'.format(self.name), 0, -1)

    def _in_edges(self):
        return list(self.graph.redis.smembers('{}:ie'.format(self.name)))

    def _out_edges(self):
        return list(self.graph.redis.smembers('{}:oe'.format(self.name)))

    def properties(self):
        return self.p._properties()


class Edge(object):
    """allows access to graph edge properties, and adjacent nodes.
        in_node()/out_node(): adjacent nodes
        properties(): dict of edge properties

        accessing/modifying/deleting individual properties:
        the same way as with Node's, see node docstring.
        """
    def __init__(self, graph, id):
        self.graph = graph 
        self.id = str(id)
        self.name = graph.name + ':e:' + self.id
        self.p = Properties(self.graph, self.name)

    def in_node(self):
        return Node(self.graph, self._in_node()) 

    def out_node(self):
        return Node(self.graph, self._out_node()) 

    def _in_node(self):
        return self.graph.redis.get('{}:in'.format(self.name))

    def _out_node(self):
        return self.graph.redis.get('{}:on'.format(self.name))

    def properties(self):
        return self.p._properties()


class Properties(object):
    """This is internal to the Node/Edge classes, you won't use it directly."""
    def __init__(self, graph, name):
        d_ = self.__dict__
        d_['_graph'] = graph
        d_['_name'] = name

    def __setattr__(self, name, value): 
        d_ = self.__dict__
        #TODO don't let people make attributes that are in d_, or something blah
        #dbname, type, id = d_['_name'].split(':')
        if d_['_graph'].redis.hget('{}:p'.format(d_['_name']), name):
            old_value = d_['_graph'].redis.hget('{}:p'.format(d_['_name']), name)
            d_['_graph']._deindex(d_['_name'], name, old_value)
        d_['_graph'].redis.hset('{}:p'.format(d_['_name']), name, value)
        d_['_graph']._index(d_['_name'], name, value)

    def __getattr__(self, name):
        d_ = self.__dict__
        val = d_['_graph'].redis.hget('{}:p'.format(d_['_name']), name)
        if not val: 
            raise AttributeError(name)
        return val
 
    def __delattr__(self, name):
        d_ = self.__dict__
        value = d_['_graph'].redis.hget('{}:p'.format(d_['_name']), name)
        exists = d_['_graph'].redis.hdel('{}:p'.format(d_['_name']), name)
        if exists == 0:
            raise AttributeError(name)
        d_['_graph']._deindex(d_['_name'], name, value)

    def _properties(self):
        d_ = self.__dict__
        return d_['_graph'].redis.hgetall('{}:p'.format(d_['_name']))


def main(argv=None):
    logging.debug("TODO: I guess some kind of test harness would go here")
    return 0

if __name__ == '__main__':
    status = main()
    sys.exit(status)
