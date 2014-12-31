#rgr.py

a graph database for Python, built on Redis

###Goal:

- Pythonic, simple, flexible, unassuming graph database.


###Prerequisites:

- Redis server
- redis.py

###Usage: 

```python
from rgr import Graph 

g = Graph()

jack = g.add_node(name='jack')
jill = g.add_node(name='jill', gender='female') #multiple properties

g.add_node(name='fred') #it's there even if you didn't keep the Node object

g.add_edge(jack, jill, rel='knows')
g.add_edge(jill, jack, rel='hates', weight=100) #set however many properties you want

fred = g.get_nodes(name='fred') #get nodes

haters = g.get_edges(rel='hates') #get edges
for h in haters:
  print h.in_node().prop.name #incoming node - 'name' property

jnodes = g.find_nodes(name="^[Jj]") #regex queries

jack.prop.on = 'the hill' #set and access properties by 'prop' object that manages properties
jill.prop.has = 'a pail'  #is this 'prop' Properties object a bad idea?
                          #maybe it should just act like a dict? idk

for node in jack.children():
    print node.properties() 

########    
# some more advanced stuff:
########

younguns = filter(lambda n: n.prop.age < 30, g.get_nodes(type='person'))
middle_aged = filter(lambda n: (n.prop.age >= 30) and (n.prop.age < 50), g.get_nodes(type='person'))

#only people with names set
print [x.properties() for x in filter(lambda n: n.prop.name, g.get_nodes(type='person')]
# [{'age': '54', 'name': 'bob', 'type': 'person'}, {'age': '12', 'name': 'jake', 'type': 'person'}, 
# {'age': '28', 'name': 'brenna', 'type': 'person'}, {'age': '28', 'name': 'foo', 'type': 'person'}]

#whoever added these guys to the database is in big trouble
print [x.properties() for x in filter(lambda n: not n.prop.name, g._nodes())]
# [{'age': '35', 'type': 'person'}, {'age': '34.2', 'type': 'person'}, 
# {'age': '999', 'type': 'person'}]


haters = [x.in_node() for x in g.get_edges(rel='hates')] #a better way to find the haters

```
###Todo:

- make operations atomic - right now this library is NOT thread safe
- make code more idiomatic

#####Misc:
- test, debug, standardize/cleanup
- 
###Benchmarks/Tests I've done :

12/29/2014: using using the version of test.py in the repo today, i added 100,000 nodes and 500,000 edges with between 3-5 totally random properties each (anywhere from 2-20 chars i believe for the key and value) and one 'name' property with a random string as the value. Each object was about 160 bytes on average, including the element data and indices; my 1.8Ghz celeron laptop added about 175-200 elements per second; altogether, these 600,000 elements took up 950MB of memory within redis. I also deleted each node one by one, which I didn't time, but i would guess it was at around 100 nodes per second (when a node is deleted, all adjacent edges are deleted as well). The only operation that isn't constant time is find_nodes(), which for 100,000 elements took 12 seconds and for 500,000 elements took a minute. (go figure ;P)

I'd like to do more tests with more realistic data sets and see how it behaves. find() functions are gonna be linear to the number of nodes you have anyway, but I'd like to see how much data is used up by each nodes when you don't have so much unique random property data. I'd think it would be quite a bit less because of the way indexing works if nodes/edges have properties in common.

it could probably be sped up by doing some clever pipelining, but I haven't started on that yet.
