import types

class NamedIndex(object):
    def __init__(self, name):
        self.name = name

class NamedIndexes(object):
    """Originally part of the PhaseRunner, I liked this code, so I didn't throw it out (for use
    in another program at some point, when I moved PhaseRunner to a simplified model). The crux
    of the code is in the __getitem__() function. The rest is just simple wrapping"""
    def __init__(self):
        self._indexes = []
        
    def add_index(self, index_name):
        if not self.index_exists(index_name):
            self._indexes.append(NamedIndex(index_name))
        
    @property
    def index_names(self):
        return [i.name for i in self._indexes]
    def index_exists(self, index_name):
        return index_name in self.index_names
    
    def __getitem__(self, index): #Will also handle slices
        #This override of "getitem" is a way to handle "named slices" organically
        #If you have 4 indexes, named "A", "B", "C", and "D", instead of remembering
        #that they're "1,2,3,4" numerically, you can simply use their names in the
        #slice -- for instance instance[B:D] will return [B,C,D]
        def __search_index(name):
            #Return the index for the given slice 
            for ix, indexobj in enumerate(self._indexes):
                if name.lower() == indexobj.name.lower():
                    return ix
            return None
    
        if isinstance(index, types.IntType):
            #Single numeric index
            return self._indexes[index]
        elif isinstance(index, types.StringType):
            #Single string index
            si = __search_index(index)
            if si is not None:
                return self._slices[si]
            else:
                raise exceptions.IndexError("String Index '%s' not found in slices" % index)
        elif isinstance(index, types.SliceType):
            #Slice, can contain numbers or keys
            slice_start = index.start
            slice_stop = index.stop
            slice_step = 1 #For now, only support single steps in one direction... will change if there's a use-case
            if isinstance(slice_start, types.StringType):
                si = __search_index(slice_start)
                if si is not None:
                    slice_start = si
                else:
                    raise exceptions.IndexError("Start String Index '%s' not found in slices" % slice_start)
            if isinstance(slice_stop, types.StringType):
                si = __search_index(slice_stop)
                if si is not None:
                    slice_stop = si
                else:
                    raise exceptions.IndexError("Stop String Index '%s' not found in slices" % slice_stop)
                slice_stop += 1 #Unlike normal slices, named slices are end-inclusive

            try:
                slice_object = slice(slice_start, slice_stop, slice_step)
            except Exception, e:
                raise exceptions.IndexError("Start Index %s and Stop Index %s form an invalid slice: %s" % (index.start, index.stop, e.message))
            
            return self._indexes[slice_object]

if __name__ == '__main__':
    ni = NamedIndexes()
    
    ni.add_index("Dog")
    ni.add_index("Chicken")
    ni.add_index("Hawk")
    ni.add_index("Cat")
    ni.add_index("Elephant")
    
    print ni.index_names
    
    sublist = ni["Chicken":"Cat"]
    for index in sublist:
        print index.name