import exceptions
import types
import copy
import logging
import argparse
import utils

LOGGER = utils.configure_log()

class PhaseRunnerError(exceptions.Exception):
    pass

class PhaseRunnerPhase(object):
    """Implementation of the individual named phase."""
    def __init__(self, phase_name, phase_function, required_args = None, optional_args = None, outputs = None, arg_pool = None, stop_on_fail = True):
        """Init
     
        Parameters:
        phase_name (string): Name of the phase
        phase_function (function): Pointer to the class's function
        required_args (list): List of argument names that are required for this runner
        optional_args (list): List of argument names that are optional for this runner
        outputs (list): List of output arguments that will be produced by this runner
        arg_pool (dict): Dictionary that contains the input arguments for the runner (and will be used for output from it)
        stop_on_fail (boolean): Whether or not to stop the run after this runner fails
        """
        self._name = phase_name
        self._function = phase_function
        self._required_args = required_args
        self._optional_args = optional_args
        self._outputs = outputs
        self._arg_pool = arg_pool
        self._stop_on_fail = stop_on_fail
        self._status = None
        
    @property
    def name(self): return self._name
    @property
    def function(self): return self._function
    @property
    def required_args(self): return self._required_args
    @property
    def optional_args(self): return self._optional_args
    @property
    def returns(self): return self._returns
    @property
    def args(self): return self._arg_pool
    @property
    def stop_on_fail(self): return self._stop_on_fail
    @property
    def status(self): return self._status
    
    def run(self):
        """Execute this phase.
        
        Returns:
            The status of this execution
        """
        #Process Arguments
        function_args = {}

        if self._arg_pool is not None:
            #Check required arguments
            missing_args = []
            if self.required_args:
                for req_arg in self.required_args:
                    if req_arg not in self._arg_pool.keys():
                        missing_args.append(req_arg)
                    else:
                        function_args[req_arg] = self._arg_pool[req_arg]
                if len(missing_args) > 0:
                    raise PhaseRunnerError("The following arguments are required by phase %s: %s" % (self._name, ", ".join(missing_args)))
            #Add optional args if they've been provided
            if self._optional_args:
                for opt_arg in self._optional_args:
                    if opt_arg in self._arg_pool.keys():
                        function_args[opt_arg] = self._arg_pool[opt_arg]
        
        #Run the function, and set output variables (if requested)
        #Note that the first value returned from all functions must be the success of the function
        #Also, if the function throws an exception, it isn't caught here (to work like any other function)
        return_vals = self._function(**function_args)
        if return_vals is None:
            return_vals = [True] #Assume passed for functions that return nothing
        if isinstance(return_vals, types.BooleanType): #Returned only True or False
            return_vals = [return_vals]
            
        #Check to make sure the first item is True or False. If not, raise an error
        if not isinstance(return_vals[0], types.BooleanType):
            raise PhaseRunnerError("Phase %s needs to return a boolean as its first value or not return anything" % self._name)
        
        #The first result is whether the function passed or not. This should be "True" if it's just a utility function.
        self._status = return_vals[0]
        
        #Parse through outputs, raising an exception if there are too few
        if self._outputs:
            if len(return_vals) < (len(self._outputs) + 1):
                raise PhaseRunnerError("Expected return values for phase %s: %s. The function only returned: %s" % (self._name, ", ".join(self._outputs), ", ".join(return_vals[1:])))
            #With the list of "outputs", put the return value from the function into the corresponding slot in the arg pool
            for index, rv in enumerate(self._outputs):
                self._arg_pool[rv] = return_vals[index + 1]
                
        return self._status

class PhaseRunner(object):
    """Runs a series of phases."""
    def __init__(self, *args, **kwargs):
        self._phases = []   #List of phases
        self._arg_pool = copy.copy(kwargs) or {}    #The argument pool should be primed with the passed keyword arguments
        self._stop_on_fail = kwargs.get("stop_on_fail") or True #This is the stop_on_fail for the entire runner.
                                                                #Each phase can set its own as well
        self._first_phase = None
        self._last_phase = None
        
    def add_phase(self, phase_name, phase_function, required_args = None, optional_args = None, outputs = None, *args, **kwargs):
        """Add a phase to this runner.
        
        Parameters:
        phase_name (string): Name of the phase. Must be unique to this runner
        phase_function (function): Pointer to the class's function
        required_args (list): List of argument names that are required for this runner
        optional_args (list): List of argument names that are optional for this runner
        outputs (list): List of output arguments that will be produced by this runner
        stop_on_fail (boolean - Optional): Whether or not to stop this individual phase 
        """
        #Make sure phase name is unique
        if not self.phase_exists(phase_name):
            #Set stop_on_fail for the phase if provided. Otherwise, use the default from the runner
            stop_on_fail = kwargs["stop_on_fail"] if "stop_on_fail" in kwargs else self._stop_on_fail
            self._phases.append(PhaseRunnerPhase(phase_name, phase_function, required_args, optional_args, outputs, arg_pool = self._arg_pool, stop_on_fail = stop_on_fail))
        else:
            raise PhaseRunnerError("Phase %s already exists in runner. Cannot add more than once." % phase_name)
        
    @property
    def args(self):
        return self._arg_pool
    @args.setter
    def args(self, new_args):
        self._arg_pool.update(copy.copy(new_args))
    
    @property
    def phase_list(self):
        return [p.name for p in self._phases]

    def phase_exists(self, phase_name):
        """Returns true if the phase name exists already"""
        return phase_name in self.phase_list
    
    def cli_setup_args(self, arg_parser):
        """Build the cli argument group for the PhaseRunner, and add it to the passed parser"""
        phase_group = arg_parser.add_argument_group("Optional Test Phase Selection", "You can specify a start and end phase to execute. They must be in-order from the phase list.\nValid Phases: %s" % ",".join(self.phase_list))
        phase_group.add_argument("--startwith", "-s", action="store", help="Specify the test phase to start with")
        phase_group.add_argument("--endwith", "-e", action="store", help="Specify the test phase to end with (inclusive)")
        phase_group.add_argument("--exact", "-x", action="store", help="The exact (and only) phase to run. Cannot be used with startswith/endswith")
    
    def cli_parse_args(self, args, arg_parser):
        """Handles arguments pertinent to the PhaseRunner. Requires the args (as returned by
           arg_parser.parse()) and the argument parser object."""
        #Check which phases we're running. Return errors if there's a problem
        if (args.startwith or args.endwith) and args.exact:
            arg_parser.error("Both --exact and (--startwith/--endwith) cannot be used at the same time")
        if args.startwith and args.startwith not in self.phase_list:
            arg_parser.error("Start Phase %s not in allowed phases: %s" % (args.startwith, ", ".join(self.phase_list)))
        if args.endwith and args.endwith not in self.phase_list:
            parser.error("End Phase %s not in allowed phases: %s" % (args.endwith, ", ".join(self.phase_list)))
        if args.exact and args.exact not in self.phase_list:
            parser.error("Phase %s not in allowed phases: %s" % (args.exact, ", ".join(self.phase_list)))
        
        #Setup phase bounds
        if args.startwith:
            self._first_phase = args.startwith
        if args.endwith:
            self._last_phase = args.endwith
        if args.exact:
            self._first_phase = self._last_phase = args.exact

        #Create an argument dictionary by taking the argument list and removing all null
        #and PhaseRunner arguments
        self.args = dict([(k,v) for (k,v) in args._get_kwargs() if k not in ("startwith", "endwith", "exact") and v is not None])
    
    @property
    def stop_on_fail(self): return self._stop_on_fail
    @stop_on_fail.setter
    def stop_on_fail(self, value): self._stop_on_fail = value
    
    def _get_phase_index(self, phase_name):
        index = -1
        for temp_index, phase in enumerate(self._phases):
            if phase.name.lower() == phase_name.lower():
                index = temp_index
                break
        return index
    
    def _get_phases(self, first_phase, last_phase):
        first_index = last_index = 0
        first_index = 0 if first_phase is None else self._get_phase_index(first_phase)
        last_index = (len(self._phases)) if last_phase is None else (self._get_phase_index(last_phase) + 1) #Using len instead of -1 because of the return of a later condition
        if first_index == -1:
            raise exceptions.IndexError("First Phase %s not in phases" % first_phase)
        if last_index == -1:
            raise exceptions.IndexError("Last Phase %s not in phases" % last_phase)
        if last_index < first_index:
            raise PhaseRunnerError("First Phase %s must be earlier in the phase list than Last Phase %s" % (first_phase, last_phase))
        return self._phases[first_index:last_index] if last_index > first_index else self._phases[first_index]
    
    def run_phases(self, first_phase = None, last_phase = None):
        #Setup slice. Priority: function argument > instance parameter (cli) > None
        first_phase = first_phase or self._first_phase
        last_phase = last_phase or self._last_phase
        phases = self._get_phases(first_phase, last_phase)
        
        #Execute function pre_run() if it exists in class
        if hasattr(self, "pre_run"):
            LOGGER.info("Running pre-run function...")
            LOGGER.info("-" * 40)
            try:
                success = self.pre_run()
            except Exception, e:
                LOGGER.error("Error in pre-run: %s" % e.message)
                success = False
            if self._stop_on_fail and not success:
                LOGGER.error("Pre-run failed and Stop_On_Fail is set. Stopping run.")
                return False
        else:
            LOGGER.info("No pre-run. Skipping.")
        LOGGER.info("=" * 40)
            
        #Now, execute all of the phases
        for phase in phases:
            LOGGER.info("Running Phase %s..." % phase.name)
            LOGGER.info("-" * 40)
            try:
                success = phase.run()
            except Exception, e:
                LOGGER.error("Error in phase '%s': %s" % (phase.name, e.message))
                success = False
            finally:
                LOGGER.info("...Phase %s Complete" % phase.name)
            if not success:
                if self._stop_on_fail and phase.stop_on_fail:
                    LOGGER.error("Phase '%s' failed and Stop_On_Fail is set. Stopping run." % phase.name)
                    return False
                else:
                    LOGGER.info("Phase %s failed, but Stop_On_Fail not set (for either phase or whole runner). Run continuing." % phase.name)
            LOGGER.info("=" * 40)

        #Now, execute "post_run" if it exists
        if hasattr(self, "post_run"):
            LOGGER.info("Running post-run function...")
            LOGGER.info("-" * 40)
            try:
                success = self.post_run()
            except Exception, e:
                LOGGER.error("Error in post-run: %s" % e.message)
                success = False
            if self._stop_on_fail and not success:
                LOGGER.error("Post-run failed and Stop_On_Fail is set. Stopping run.")
                return False
        else:
            LOGGER.info("No post-run. Skipping.")
        LOGGER.info("=" * 40)
        
        #Finally, log the results
        LOGGER.info("Run Complete. Phase Status:")
        for phase in phases:
            LOGGER.info("    %s: %s" % (phase.name, str(phase.status).capitalize()))

if __name__ == '__main__':
    def a_func(number):
        LOGGER.info("A")
        LOGGER.info("Number: %d" % number)
        return True, "mystring"
    def b_func(): LOGGER.info("B")
    def c_func(a_string):
        LOGGER.info("C should fail")
        LOGGER.info("A String: %s" % a_string)
        return False
    def d_func():
        LOGGER.info("D")
    def e_func():
        LOGGER.info("E")
    
    p = PhaseRunner(number = 19)
    p.add_phase("Phase A", a_func, required_args = ["number"], optional_args = None, outputs = ["a_string"])
    p.add_phase("Phase B", b_func)
    p.add_phase("Phase C", c_func, ["a_string"])
    p.add_phase("Phase D", d_func)
    p.add_phase("Phase E", e_func)

    p.stop_on_fail = False
    p.run_phases()
    
    p.stop_on_fail = True
    p.run_phases()
    
    p.stop_on_fail = False
    p.run_phases("Phase B", "Phase D")