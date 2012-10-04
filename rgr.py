#!/usr/bin/env python
""" rgr.py - a Graph Database built on Redis """

import sys
import redis_natives
from redis_natives.datatypes import Primitive, Set, List, Dict
from redis import Redis
import logging
import re

#logging.basicConfig(level=logging.CRITICAL)
logging.basicConfig(level=logging.DEBUG)

__all__ = (
    "Graph",
    "Node",
    "Edge",
)

class Graph(object):
    """
        Main interface for creating/removing/looking up graph elements.

        prereq's:

        - Redis server 
        - redis.py
        - redis_natives 
        
        usage: 
        
        from rgr import *
        
        g = Graph('mygraph') 

        # where 'mygraph' is the DB name in Redis. default is 'rgr'.
        # in the above example, all keys for this graph in Redis will
        # be prepended with 'mygraph:'

        node = g.addn(name='john',multiproperty=[1,2,3]) 
        node2 = g.addn(name='mary',multiproperty=[1,2,3]) 

        # add a node to the graph. returns a Node() object. Takes an 
        # arbitrary number of **kwargs and adds them to the new node
        # as properties. All properties are stored as lists in Redis, 
        # but you can still use them as strings when they have a single
        # value.

        edge = g.adde(node, node2, rel="knows")
        edge = g.adde(1, 0, rel="hates")

        # add an edge from node1 to node2 (or between 2 node ID's). 
        # (or a node and an ID for that matter)
        # takes and arbitrary number of **kwargs as properties.

        n = g.getn(name='john')
        e = g.gete(rel='knows')

        # returns an element or list of elements (depending on the case) 
        # thkt match the given **kwargs. This method implements an
        # exact lookup (no wildcards).
            
        g.deln(0)
        g.dele(0)

        # delete an element from the graph with the given ID.
        # deleting a node also deletes its adjacent edges.
        
        
        all_node_ids = g.nodes 
        all_edge_ids = g.edges

        #or, as generators yielding Node/Edge objects:

        for n in g.nodes(): 
            print n._id
        for e in g.edges():
            print e._id

        # Set() of all node / edge ids currently in graph.
        # ( redis_natives.datatypes.Set type )

        TODO: 
        what if redis server not on localhost:6379 ?
        g.query() and related (Indexer.query())
    
    """

    def __init__(self, name='rgr'):
        """
            parameters: 
            ..name: optional  
            ....graph name in Redis. Keys in Redis are 
            ....prepended with name+':'

            returns:
            ..Graph() object
            
        """
        self.name = name
        self.rc = Redis()
        self.index = Indexer(self)
        if self.rc.exists(name+":nextnid"):
            self.nextnid = Primitive(self.rc,name+':nextnid')
        else:
            self.nextnid = Primitive(self.rc,name+':nextnid',0)
        if self.rc.exists(name+":nexteid"):
            self.nexteid = Primitive(self.rc,name+':nexteid')
        else: 
            self.nexteid = Primitive(self.rc,name+':nexteid',0)
        self.nodes = NodeSet(self.rc, self, name+':nodes')
        self.edges = EdgeSet(self.rc, self, name+':edges')

    def addn(self, **kwargs):
        """        
            add node to graph.
            
            parameters:
            ..kwargs: optional
            ....property key='value' or key=['values'] pairs 

            returns:
            ..Node() object just created.

        """
        n = Node(self, self.nextnid.value)
        for k in kwargs:
            n.__setattr__(k, kwargs[k])
        self.nodes.add(self.nextnid.value)
        self.nextnid.incr()
        return n
        
    def getn(self, **kwargs):
        """
            Look up graph nodes.
            
            Parameters:
            ..kwargs: optional
            ....key='value' pairs to look up. Returns the 
            ....intersection of results found for each key
            ....(AND operation). 

            Returns: 
            ..list(): of Node's if any are found.
                
        """
        nodes = []
        for n in self.index.lookup('n', **kwargs):
           # yield Node(self,n)
            nodes.append(Node(self,n))
            return nodes

    def queryn(self, **kwargs):
        """
            regex lookup of nodes by property.
            kwargs are re strings.

        """
        return self.index.query('n',**kwargs)

    def deln(self, node):
        """
            delete node by id or Node() object.

            Parameters:
            ..node: required
            ....Node or node ID to remove from graph.

            Note: if by object, you'll want to also 'del node_obj'.

        """
        if type(node) is int:
            if node not in self.nodes:
                raise ValueError(node)
            n = Node(self,node)
        elif type(node) is Node:
            n = node 
        elif type(node) is str:
            if int(node) not in self.nodes:
                raise ValueError(node)
            n = Node(self,int(node))
        else:
            raise TypeError("node type was '{}', {} :(".format(node, type(node)))

        for ie in n._ie:
            if ie in self.edges:
                self.dele(ie)
            else:
                logging.debug("Warn: Consistency error: "\
                    "tried to remove nonexistent incoming edge "\
                    "({}) from node ({}) - edge not in Graph.edges ".format(ie, n._id))
        for oe in n._oe:
            if oe in self.edges:
                self.dele(oe)
            else:
                logging.debug("Warn: Consistency error: "\
                    "tried to remove nonexistent outgoing edge "\
                    "({}) from node ({}) - edge not in Graph.edges".format(ie, n._id))
        
        for prop in n._p:
            self.index.rm('n',n._id,prop,n._properties[prop])
            if self.rc.exists(n._properties[prop].key):
                self.rc.delete(n._properties[prop].key)
        
        if self.rc.exists(n._p.key):
            self.rc.delete(n._p.key)
        if self.rc.exists(n._pn.key):
            self.rc.delete(n._pn.key)
        if self.rc.exists(n._cn.key):
            self.rc.delete(n._cn.key)
        if self.rc.exists(n._ie.key):
            self.rc.delete(n._ie.key)
        if self.rc.exists(n._oe.key):
            self.rc.delete(n._oe.key)
        self.nodes.remove(n._id)
 
    def adde(self, parent, child, **kwargs):
        """
        add edge to graph.
         
        Parameters:
        ..parent: required
        ....Node or node id of start node.
        ..child: required
        ....Node or node id of end node.
        ..kwargs: optional
        ....key='value' properties to add to Edge
       
        Returns:        
        ..Edge() just created.

        """
        e = Edge(self, self.nexteid.value)
        for k in kwargs:
            e.__setattr__(k, kwargs[k])
        self.edges.add(self.nexteid.value)

        if type(parent) is Node: 
            pn = parent
        elif type(parent) is int: 
            pn = Node(self,parent)
        elif type(parent) is Primitive or type(parent) is NodePrimitive:
            pn = Node(self,parent.value)
        elif type(parent) is str:
            pn = Node(self,int(parent))
        else:
            raise TypeError("parent type was '{}', {} :(".format(parent, type(parent)))

        if type(child) is Node:
            cn = child 
        elif type(child) is int:
            cn = Node(self,child)
        elif type(child) is Primitive or type(child) is NodePrimitive:
            cn = Node(self,child.value)
        elif type(child) is str:
            cn = Node(self,int(child))
        else:
            raise TypeError("child type was '{}', {} :(".format(child, type(child)))
       

        e._in.value = pn._id
        e._on.value = cn._id

        if str(cn._id) not in pn._cn:
            pn._cn[str(cn._id)] = 1
        else:
            pn._cn.incr(str(cn._id))

        if str(pn._id) not in cn._pn:
            cn._pn[str(pn._id)] = 1
        else:
            cn._pn.incr(str(pn._id))
        
        pn._oe.add(e._id)
        cn._ie.add(e._id)
        
        self.nexteid.incr()
        return e

    def gete(self, **kwargs):
        """
            Look up graph edges.
            
            Parameters:
            ..kwargs: optional
            ....key='value' pairs to look up. Returns the 
            ....intersection of results found for each key
            ....(AND operation). 

            Returns: 
            ..list(): of Edge's, if any are found.
            
        """
        edges = []
        for e in self.index.lookup('e', **kwargs):
        #    yield Edge(self,e)
            edges.append(Edge(self,e))
            return edges 

    def querye(self, **kwargs):
        """
            regex lookup of edges by property.
            kwargs are re strings.

        """
        return self.index.query('e',**kwargs)
    def dele(self, edge):
        """
            delete edge by id or Edge() object.
            Parameters:
            ..edge: required
            ....Edge or edge ID to remove from graph.

            Note: if by object, you'll want to also 'del edge_obj'.

        """
        if type(edge) is int:
            e = Edge(self, edge)
        elif type(edge) is Edge:
            e = edge
        elif type(edge) is str:
            e = Edge(self,int(edge))
        else:
            raise TypeError("edge type was '{}', {} :(".format(edge, type(edge)))
       
        parent = None
        child = None

        if e._in in self.nodes:
            parent = Node(self, e._in.value)
            if str(e._id) in parent._oe:
                parent._oe.remove(e._id)
            else:
                logging.debug("Warn: Consistency error:" \
                    "edge ({}) not listed in "\
                    "parent._oe ({})".format(e._id, parent._id))
        else:
            logging.debug("Warn: Consistency error: edge ({}) refers"\
                "to nonexistent incoming node ({})".format(e._id, e._in))

        if e._on in self.nodes:
            child = Node(self, e._on.value)
            if str(e._id) in child._ie:
                child._ie.remove(e._id)
            else:
                logging.debug("Warn: Consistency error: "\
                    "edge ({}) not listed in "\
                    "child._ie ({})".format(e._id, child._id))
        else: 
            logging.debug("Warn: Consistency error: edge ({}) refers "\
                "to nonexistent outgoing node ({})".format(e._id, e._in))
        if parent and child:
            
            if str(child._id) in parent._cn:
                if parent._cn[str(child._id)] == '1':
                    del parent._cn[str(child._id)]
                else: #assert >= 1
                    parent._cn.incr(str(child._id), -1)
            else:
                logging.debug("Warn: consistency: child._id not in parent's child node list")

            if str(parent._id) in child._pn:
                if child._pn[str(parent._id)] == '1':
                    del child._pn[str(parent._id)]
                else:
                    child._pn.incr(str(parent._id), -1)
            else:
                logging.debug("warn: consistency: parent._id not in child's parent node list")
        elif parent and not child: 
            if str(e._on) in parent._cn:
                del parent._cn[str(e._on)]
            else:
                logging.debug("Warn: consistency: e._on not in parent's child node list")
            logging.debug("warn: child node doesn't exist")
        elif not parent and child: 
            if str(e._in) in child._pn:
                del child._pn[str(e._in)]
            else:
                logging.debug("Warn: consistency: e._in not in parent's child node list")
            logging.debug("warn: parent node doesn't exist")
        else:
            logging.debug("Warn: Consistency error: parent/child node inconsistent")

        for prop in e._p:
            self.index.rm('e',e._id,prop,e._properties[prop])
            if self.rc.exists(e._properties[prop].key):
                self.rc.delete(e._properties[prop].key)
            else:
                logging.debug("Warn: Consistency: e._properties['{}'] not in redis".format(
                        e._properties[prop]))
        if e._id in self.edges:
            self.edges.remove(e._id)
        else:
            logging.debug("Warn: Consistency: e({}) not in self.edges".format(e._id))
        if self.rc.exists(e._in.key):
            self.rc.delete(e._in.key)
        if self.rc.exists(e._on.key):
            self.rc.delete(e._on.key)
        if self.rc.exists(e._p.key):
            self.rc.delete(e._p.key)

    def _dump(self):
        """
            dumps all graph data to 
            stdout in human-readable format.
        
        """
        print '===================='
        print 
        print "nodes:", g.nodes
        print "edges:", g.edges
        print "redis keys:"
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


class GraphElement(object):
    def __setattr__(self, name, value):
        """ 
            (abstract?) Base class for Node's and Edges. 

            all properties get placed into _properties dict
            unless they are instantiated during __init__.
            I stole a couple of lines from bulbflow to 
            make that happen.

        """
        #begin stolen from bulbflow:
        dict_ = self.__dict__
        _initialized = dict_.get("_initialized", False)
        if name in dict_ or _initialized is False:
        #end stolen from bulbflow
            object.__setattr__(self, name, value)
        else:
            self._properties[name] = IndexList(self._graph.rc, self, name, self._name+":p'"+name+"'") 
            if len(self._properties[name]) == 0:
                self._properties[name].append(value) #append calls Indexer.update
                self._p.add(name)
            else:
                #remove and re-add property - index updated on re-add
                if self._graph.rc.exists(self._properties[name].key):
                    self._graph.rc.delete(self._properties[name].key)
                self._p.remove(name)
                self.__setattr__(name, value)
        
    def __getattr__(self, name):
        """
            python ignores this if it finds something in
            __dict__, otherwise, search _properties and
            throw an error if you try to access a property that
            doesn't exist.
        """
        try:
            return self._properties[name]
        except:
            raise AttributeError(name)

    def __delattr__(self, name):
        """
            delete an attribute from an element.
            i.e. `del node.foo` removes 'foo' from
            redis and the index.
        """
        self._graph.index.rm(self._type, self._id, name, self._properties[name])
        del self._properties[name]
        self._p.remove(name)
        if self._graph.rc.exists(self._name+":p'"+name+"'"):
            self._graph.rc.delete(self._name+":p'"+name+"'")

  
class Node(GraphElement):
    """
        Represents a graph node. You probably won't often need
        to create these directly, but you can without issue (so long
        as it already exists in the graph).

        As it relates to Redis:
        - Node data is read directly from Redis when a Node() is instantiated.
        - Changes to a Node() are immediately reflected in Redis.
        - Changes to Redis from an outside source would (I believe) be immediately
        reflected by the Node()
        - del node_obj doesn't delete any data from redis.

        usage:
        
        g = Graph()
        n = g.addn()

        Node properties:

        #set a node property: these are auto indexed:
        
        n.name = "fred"
        # or:
        n.__setattr__('name','fred')

        Node data: 

        data members themselves only contain Node/Edge ID's. However,
        if you call() them, you'll be given a generator which yields
        their corresponding Node/Edge object.

        Callable data members are:
        _oe, _ie, _pn, _cn
        
        n._pn # might produce set(0,5,12)

        for i in n._pn(): print i
        # would produce :
        # <rgr.Node object at 0xdeadbeef>
        # <rgr.Node object at 0x...>
        # <rgr.Node object at 0x...>

        type is redis_natives.datatypes.Set:

        n._p          # keys of a node's properties
        n._properties # dict of node's property data
           
        type rgr.EdgeSet: 

        n._oe         # outgoing edge IDs 
        n._oe()       # generator producing outgoing Edge's
        n._ie         # incoming edge IDs
        n._ie()       # generator producing incoming Edge's
           
        Type rgr.NodeDict: 

        n._pn         # parents' IDs and the number of edges coming from each 
        n._pn()       # generator producing all parent nodes
        n._cn         # childrens' IDs and the number of edges going to each
        n._cn()       # generator producing all child nodes
        # don't edit this stuff directly.  

    """
    def __init__(self,graph,id):
        """
            initialize a Node.

            Parameters:
            ..graph: required
            ....parent Graph() object
            ..id: required
            ....ID that the node will use. If it doesn't exist 
            ....in redis, it will be created there. Don't create
            ....new nodes directly, though, because Graph() keeps
            ....track of created nodes via Graph.addn().

            Returns:
            ..Node() 

        """
        self._properties = {} 
        self._graph = graph
        self._id = int(id)
        self._type = 'n'
        self._name = ':'.join([graph.name,self._type,str(id)])
        self._p = Set(graph.rc, ':'.join([self._name,'p']))
        self._ie = EdgeSet(graph.rc, self._graph, ':'.join([self._name,'ie']))
        self._oe = EdgeSet(graph.rc, self._graph, ':'.join([self._name,'oe']))
        self._pn = NodeDict(graph.rc, self._graph, ':'.join([self._name,'pn']))
        self._cn = NodeDict(graph.rc, self._graph, ':'.join([self._name,'cn']))
        for prop in self._p:
            self._properties[prop] = IndexList(self._graph.rc, self, prop, self._name+":p'"+prop+"'")
            self._graph.index.add(self._type, self._id, prop, self._properties[prop])
        self._initialized = True
  
  
class Edge(GraphElement):
    """
        Represents a graph edge. You probably won't often need
        to create these directly, but you can without issue (so long
        as it already exists in the graph).

        As it relates to Redis, the same rules apply as for Node()'s.

        usage:
    
        g = Graph()
        n1 = g.addn()
        n2 = g.addn()

        e = g.adde(n1,n2,rel="knows")
        nid1, nid2 = n1._id, n2._id    # id is an int()
        e2 = g.adde(nid2,nid1,rel="hates")

        Edge properties:

        #set an edge property: these are auto indexed:
    
        e.weight = 1 
        # or:
        e2.__setattr__('how_much','a lot!')

        Edge data (private): 

        callable: 
        _in, _on
        
        type is redis_natives.datatypes.Set:

        e._p          # keys of a edge's properties

        type is rgr.NodePrimitive:

        e._in         # incoming node ID
        e._in()       # incoming Node()
        e._on         # outgoing node ID 
        e._on()       # outgoing Node()

        regular python dict(): 

        e._properties # dict of edge's property data
        # don't edit this stuff directly.  

    """
    def __init__(self,graph,id):
        """
            same as Node();
            see Node.__init__() docstrings for
            more information.

        """
        self._properties = {} 
        self._graph = graph
        self._id = int(id)
        self._type = 'e'
        self._name = ':'.join([graph.name,self._type,str(id)])
        self._p = Set(graph.rc, ':'.join([self._name,'p']))
        self._in = NodePrimitive(graph.rc, self._graph, ':'.join([self._name,'in']))
        self._on = NodePrimitive(graph.rc, self._graph, ':'.join([self._name,'on']))
        for prop in self._p:
            self._properties[prop] = IndexList(self._graph.rc, self, prop, self._name+":p'"+prop+"'")
            self._graph.index.add(self._type, self._id, prop, self._properties[prop])
        self._initialized = True
  

#internal functions & classes


class Indexer(object):
    """
        Class which handles indexing of node and edge properties.
        
        it's currently pretty ugly, and I'll clean it up later.
        You probably won't use it directly for anything - the only
        useful functions, lookup() and (future) query() - will be
        called by Graph() and returned to you in a more useful format.

        TODO: document & tidy up

    """
    def __init__(self, graph, indices=['n','e']):
        """set up indices"""
        self.graph = graph
        self.indices = indices
        self.index = {}
        for i in self.indices:
            self.index[i] = self.add_index(i)

    def add_index(self, name):
        """
            add index to Indexer. currently only supporting
            built-in 'n' and 'e' indices, for nodes & edges.
    
        """
        this_index = {}
        prefix = ':'.join([self.graph.name,'i',name])
        this_index['prefix'] = prefix
        this_index['property_keys'] = Set(self.graph.rc, ':'.join([prefix, 'p']))
        this_index['properties'] = {}
        for p in this_index['property_keys']:
            this_index['properties'][p] = {}
            this_index['properties'][p]["_all_values"] = Set(self.graph.rc, ':'.join([prefix,"p'"+p+"'","v"]))
            for v in this_index['properties'][p]["_all_values"]:
                this_index['properties'][p][v] = Set(self.graph.rc, ':'.join([prefix,"p'"+p+"'","v'"+v+"'"]))
        return this_index

    def add(self, i, id, name, value_list):
        """
            index the property/value(s) of an element.
            i: index name
            id: element ID
            name: name of property
            value_list: list() of values to index for given property.

            TODO: this should be private.
            TODO: only add one value at a time.
            TODO: only call update() externally.
    
        """
        self.index[i]['property_keys'].add(name) # it's a set, unique members
        if name not in self.index[i]['properties'].keys():
            self.index[i]['properties'][name] = {}
            self.index[i]['properties'][name]["_all_values"] = Set(
                self.graph.rc, 
                ':'.join([self.index[i]['prefix'],"p'"+name+"'","v"]))
        for value in value_list:
            value = str(value)
            self.index[i]['properties'][name]["_all_values"].add(value)
            if value not in self.index[i]['properties'][name].keys():
                self.index[i]['properties'][name][value] = Set(
                    self.graph.rc, 
                    ':'.join([self.index[i]['prefix'],"p'"+name+"'","v'"+value+"'"]))
            self.index[i]['properties'][name][value].add(id)
        
    def rm(self, i, id, name, value_list):
        """
            de-index the property/value(s) of an element.
            i: index name
            id: element ID
            name: name of property
            value_list: list() of values to de-index for given property.

            TODO: this should be private.
            TODO: only remove one value at a time.
            TODO: only call update() externally.
    
        """
        _props = self.index[i]['properties']
        for value in value_list:
            _props[name][value].remove(id)
            if len(_props[name][value]) == 0:
                del _props[name][value]
                _props[name]['_all_values'].remove(value)
            if len(_props[name]['_all_values']) == 0:
                del _props[name]
                self.index[i]['property_keys'].remove(name)

    def update(self, i, id, name):
        """
            when a property is modified, update the index accordingly

        """
        # TODO: duhh ... use self.index[i]!!!
        #get node property from redis
        property_key = ':'.join([self.graph.name,i,str(id),"p'"+name+"'"])
        node_property_values_list = List(self.graph.rc, property_key) 

        #get property values list from index
        index_property_values_key = ':'.join([self.graph.name,'i',i,"p'"+name+"'",'v'])
        index_property_values_set = Set(self.graph.rc, index_property_values_key)

        for value in node_property_values_list:
            indexed_ids = Set(
                self.graph.rc, 
                ':'.join([self.graph.name,'i',i,"p'"+name+"'","v'"+value+"'"])
            )
            if len(indexed_ids) == 0 or id not in indexed_ids:
                self.add(i, id, name, [value])
        for value in index_property_values_set:
            indexed_ids = Set(
                self.graph.rc, 
                ':'.join([self.graph.name,'i',i,"p'"+name+"'","v'"+value+"'"])
            )
            if id in indexed_ids:
                if value not in node_property_values_list:
                    self.rm(i, id, name, [value])
    def lookup(self, i, **kwargs):
        """
            public method, used by Graph().
            
            i: index to look through
            kwargs: properties to search

            gets matching id's for each kwarg, then
            returns the intersection of the given sets.
            (AND operation)

            return:
            ..set of matching element ID's

            TODO: check for no kwargs and do something?
            possibly or_lookup, and_lookup, etc

        """
        indices = []
        for k in kwargs.keys():
            try:
                indices.append(
                    set(
                        self.index[i]['properties'][k][kwargs[k]]
                ))
            except KeyError:
                return set()
        return set.intersection(*indices)

    def query(self, i, **kwargs):
        """
            regular expression version of lookup.
            searching for nonexistent properties will
            simply cause this function to return an empty set.
        """
        indices = []
        for k in kwargs.keys():
            search_nodes = self.get_property_members(i, k)
            if not search_nodes:
                return set() # oops, nonexistent property
            match_nodes = set()
            for sn in search_nodes:
                node = Node(self.graph, sn)
                for prop in node._properties[k]:
                    if re.search(kwargs[k], prop):
                        match_nodes.add(node)
            indices.append(match_nodes)
        return set.intersection(*indices)

    def get_property_members(self, i, name):
        """
            all elements that have a given property.
        """
        idx = self.index[i]
        try: 
            prop = idx['properties'][name]
        except KeyError:
            return set()
        values = prop['_all_values']
        nodes = set()
        for v in values:
            nodes = nodes.union(set(prop[v]))
        return nodes

class IndexList(List):
    """ 
        Extension of redis_natives.datatype.List to allow for indexing
        operations on append, remove, etc ...
        
        Each method just calls super() and then appends a call to 
        Indexer.update().

    """
    def __init__(self, client, graph_element, name, key, iter=[]):
        super(IndexList, self).__init__(client, key, iter)
        self._graph_element = graph_element
        self._name = name

    def append(self, el):
        """
            Pushes element ``el`` at the end of this list.
            extension to allow indexing.

        """
        super(IndexList,self).append(el)
        self._graph_element._graph.index.update(
            self._graph_element._type, 
            self._graph_element._id, 
            self._name)
    
    def remove(self, val, n=1, all=False):
        """
            Removes ``n`` occurences of value ``el``. When ``n`` is ``0``
            all occurences will be removed. When ``n`` is negative the lookup
            start at the end, otherwise from the beginning.
            Returns number of removed values as ``int``.

        """
        super(IndexList,self).remove(val,n,all)
        self._graph_element._graph.index.update(
            self._graph_element._type, 
            self._graph_element._id, 
            self._name)
   
    def extend(self, iter):
        """
            Extends this list with the 
            elements of ther iterable ``iter``
            
        """
        super(IndexList,self).extend(iter)
        self._graph_element._graph.index.update(
            self._graph_element._type, 
            self._graph_element._id, 
            self._name)

    def insert(self, idx, el):
        """
            Insert element ``el`` 
            at index ``idx``
            
        """
        super(IndexList,self).insert(idx,el)
        self._graph_element._graph.index.update(
            self._graph_element._type, 
            self._graph_element._id, 
            self._name)
    
    def pop(self, idx=None):
        """
            Remove and return 
            element at index ``idx``.
            
        """
        return_el = super(IndexList,self).pop(idx)
        self._graph_element._graph.index.update(
            self._graph_element._type, 
            self._graph_element._id, 
            self._name)
        return return_el

    def __repr__(self):
        """
            added for debugging. should probably
            be removed. 
            
        """
        return str([i for i in iter(self)])

    def __str__(self):
        """
            added for debugging. should probably
            be removed. 
            
        """
        return self.__repr__()


class NodeSet(Set):
    """ 
        make this a callable 
        for our own twisted purposes.

    """
    def __init__(self, client, graph, key, iter=[]):
        super(NodeSet, self).__init__(client, key, iter)
        self._g = graph
    def __call__(self):
        for i in self:
            yield Node(self._g,i)


class EdgeSet(Set):
    """ 
        make this a callable 
        for our own twisted purposes.

    """
    def __init__(self, client, graph, key, iter=[]):
        super(EdgeSet, self).__init__(client, key, iter)
        self._g = graph
    def __call__(self):
        for i in self:
            yield Edge(self._g,i)


class NodeDict(Dict):
    """ 
        make this a callable 
        for our own twisted purposes.

    """
    def __init__(self, client, graph, key, iter=None):
        super(NodeDict, self).__init__(client, key, iter)
        self._g = graph
    def __call__(self):
        for i in self:
            yield Node(self._g,i)


class NodePrimitive(Primitive):
    """ 
        make this a callable 
        for our own twisted purposes.

    """
    def __init__(self, client, graph, key, value=None):
        super(NodePrimitive, self).__init__(client, key, value)
        self._g = graph
    def __call__(self):
        if self.value is not None :
            return Node(self._g, int(self.value))
        else:
            return None

    
def main(argv=None):
    logging.debug("TODO: I guess some kind of test harness would go here"    )
    return 0

if __name__ == '__main__':
    status = main()
    sys.exit(status) 
 
