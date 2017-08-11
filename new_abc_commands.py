import sys
import os
import pyabc
import par
import tempfile
import shutil
import redirect
import optparse

from contextlib import contextmanager

def read_cmd(args):
    if len(args)==2:
        par.read_file_quiet(args[1])
    else:
        par.read_file()
    return 0

pyabc.add_abc_command(read_cmd, "ZPython", "/rf", 0)

def chdir_cmd(args):
    os.chdir( args[1] )
    return 0

pyabc.add_abc_command(chdir_cmd, "ZPython", "/cd", 0)

def pwd_cmd(args):
    print os.getcwd()
    return 0

pyabc.add_abc_command(pwd_cmd, "ZPython", "/pwd", 0)

def ls_cmd(args):
    os.system("ls " + " ".join(args[1:]))
    return 0

pyabc.add_abc_command(ls_cmd, "ZPython", "/ls", 0)

pushd_temp_stack = []

def pushdtemp_cmd(args):
    tmpdir = tempfile.mkdtemp()
    pushd_temp_stack.append( (os.getcwd(), tmpdir) )
    os.chdir(tmpdir)
    return 0
    
pyabc.add_abc_command(pushdtemp_cmd, "ZPython", "/pushdtemp", 0)

def popdtemp_cmd(args):
    prev, temp = pushd_temp_stack.pop()
    os.chdir(prev)
    shutil.rmtree(temp, ignore_errors=True)
    return 0
    
pyabc.add_abc_command(popdtemp_cmd, "ZPython", "/popdtemp", 0)

pushredirect_stack = []

def push_redirect_cmd(args):
    
    if len(args) > 1:
        dest = open(args[1], 'w')
    else:
        dest = redirect.null_file
    
    fdout = redirect.start_redirect( dest, sys.stdout)
    pushredirect_stack.append( (sys.stdout, fdout) )
    
    fderr = redirect.start_redirect( dest, sys.stderr)
    pushredirect_stack.append( (sys.stderr, fderr) )
    
    return 0
    
pyabc.add_abc_command(push_redirect_cmd, "ZPython", "/pushredirect", 0)

def pop_redirect_cmd(args):
    
    err, fderr = pushredirect_stack.pop()
    redirect.end_redirect(err, fderr)
 
    out, fdout = pushredirect_stack.pop()
    redirect.end_redirect(out, fdout)
    
    return 0
    
pyabc.add_abc_command(pop_redirect_cmd, "ZPython", "/popredirect", 0)

def print_aiger_result(args):
    status = pyabc.prob_status()
    
    if status==1:
        print 0
    elif status==0:
        print 1
    else:
        print 2
    
    return 0
    
pyabc.add_abc_command(print_aiger_result, "ZPython", "/print_aiger_result", 0)

@contextmanager
def temp_filename():

    with tempfile.NamedTemporaryFile(delete=False) as file:
        name = file.name

    try:
        yield name
    finally:
        os.unlink(name)

@contextmanager
def replace_report_result(write_cex=False, bmc_depth=False):
    
    def report_result(po, result):
        
        print "REPORT RESULT: ", po, result
        
        print >> stdout, "%d"%result
        print >> stdout, "b%d"%po

        if write_cex:
            with temp_filename() as name:
                pyabc.run_command('write_cex -a %s'%name)
                with open(name, 'r') as f:
                    stdout.write(f.read())
                        
        print >> stdout, "."
        
    def report_liveness_result(po, result):
        
        print "REPORT RESULT: ", po, result
        
        print >> stdout, "%d"%result
        print >> stdout, "j%d"%po
        print >> stdout, "."

    def report_bmc_depth(depth):
        
        print "REPORT BMC DEPTH:", depth

        if bmc_depth:
            print >> stdout, "u%d"%depth
    
    with redirect.save_stdout() as stdout:
        
        old_report_result = par.report_result
        par.report_result = report_result
        
        #old_report_liveness_result = par.report_liveness_result
        par.report_liveness_result = report_liveness_result

        old_report_bmc_depth = par.report_bmc_depth
        par.report_bmc_depth = report_bmc_depth
        
        try:
            yield
        finally:
            par.report_result = old_report_result
            #~ par.report_liveness_result = report_liveness_result
            par.report_bmc_depth = old_report_bmc_depth

def proof_command_wrapper_internal(prooffunc, category_name, command_name, change, multi=False, write_cex=False, bmc_depth=False):

    def wrapper(argv):
        
        usage = "usage: %prog [options] <aig_file>"
    
        parser = optparse.OptionParser(usage, prog=command_name)
    
        parser.add_option("-n", "--no_redirect", dest="noisy", action="store_true", default=False, help="don't redirect output")
        parser.add_option("-r", "--redirect", dest="redirect", default=None, help="redirect output to file")
        parser.add_option("-d", "--current_dir", dest="current_dir", action="store_true", default=False, help="stay in current directory")

        options, args = parser.parse_args(argv)
        
        if len(args) != 2:
            parser.print_usage()
            return 0
            
        if options.noisy and options.redirect:
            print 'error: options -n/--no_redirect and -r/--redirect are mutually exclusive'
            return 0
            
        aig_filename = os.path.abspath(args[1])

        with replace_report_result(write_cex=write_cex, bmc_depth=bmc_depth):

            if options.redirect:
                pyabc.run_command('/pushredirect %s'%options.redirect)
            elif not options.noisy:
                pyabc.run_command('/pushredirect')
                
            if not options.current_dir:
                pyabc.run_command('/pushdtemp')
                
            try:
                basename = os.path.basename( aig_filename )
                shutil.copyfile(aig_filename, basename)
                aig_filename = basename

                result = prooffunc(aig_filename)
                
                par.cex_list = []
            except:
                result = None

            if not multi:
                
                if result=="SAT":
                    par.report_result(0,1)
                elif result=="UNSAT":
                    par.report_result(0,0)
                elif type(result)==list and len(result)>0 and result[0] == "SAT":
                    par.report_result(0,1)
                elif type(result)==list and len(result)>0 and result[0] == "UNSAT":
                    par.report_result(0,0)
                else:
                    par.report_result(0,2)

            if not options.current_dir:
                pyabc.run_command('/popdtemp')

            if not options.noisy:
                pyabc.run_command('/popredirect')
                
        return 0
    
    pyabc.add_abc_command(wrapper, category_name, command_name, change)

def proof_command_wrapper(prooffunc, category_name, command_name, change, multi=False, write_cex=False, bmc_depth=False):
    def pf(aig_filename):
        par.read_file_quiet(aig_filename)
        return prooffunc()
    return proof_command_wrapper_internal(pf, category_name, command_name, change, multi, write_cex, bmc_depth)

def super_prove():
    return par.sp(check_trace=True)

proof_command_wrapper(super_prove,  'HWMCC', '/super_prove_aiger',  0, write_cex=True, bmc_depth=False)
proof_command_wrapper(par.simple,  'HWMCC', '/simple_aiger',  0, write_cex=True, bmc_depth=True)
proof_command_wrapper(par.mp,  'HWMCC', '/multi_prove_aiger',  0, write_cex=True, bmc_depth=False, multi=True)

def simple_liveness_prooffunc(aig_filename):

    try:
        import liveness
    except:
        import traceback
        traceback.print_exc()

    from pyaig import utils

    def simplify(aiger_in, aiger_out):
        print 'SIMPLIFY: start simplify', aiger_in, aiger_out
        
        with liveness.temp_file_names(2, suffix='.aig') as tmp:

            saved = utils.save_po_info(aiger_in, tmp[0])
            
            par.read_file_quiet(tmp[0])
            
            par.pre_simp()
            
            pyabc.run_command( 'write_aiger %s'%tmp[1] )

            utils.restore_po_info( saved, tmp[1], aiger_out )
            
            print 'SIMPLIFY: ended simplify'

            return True
        
    def report_result(id, res):
        
        if res and 'result' in res:
            result = res['result']
            if result=='proved':
                par.report_liveness_result(id, 0)
                return True
            elif result=='failed':
                par.report_liveness_result(id, 1)
                return True
            
        return False

    def super_prove(aiger_filename):

        par.read_file_quiet(aiger_filename)

        result = par.sp()

        if result=="SAT":
            return {'result':'failed'}
        elif result=="UNSAT":
            return {'result':'proved'}
        elif type(result)==list and len(result)>0 and result[0] == "SAT":
            return {'result':'failed'}
        elif type(result)==list and len(result)>0 and result[0] == "UNSAT":
            return {'result':'proved'}
        else:
            return {'result':'unknwon'}

    try:
        liveness.run_niklas_multi(aig_filename, simplify=simplify, report_result=report_result, super_prove=super_prove)
    except:
        import traceback
        traceback.print_exc()

proof_command_wrapper_internal( simple_liveness_prooffunc, "HWMCC", "/simple_liveness_aiger", 0, multi=True)

@contextmanager
def frame_done_callback(callback):
    old_callback = pyabc.set_frame_done_callback(callback)
    try:
        yield
    finally:
        pyabc.set_frame_done_callback(old_callback)

def bmcs_prooffunc(aig_filename):
    
    def callback(frame, po, result):
        
        if result == 0:
            par.report_bmc_depth(frame)

        print 'callback: ', frame, po, result

    pyabc.run_command('read "%s"'%aig_filename)
    pyabc.run_command('&get')

    with frame_done_callback(callback):
        pyabc.run_command('&bmcs -v')

    status = pyabc.prob_status()

    if status == pyabc.SAT:
        return 'SAT'
    elif status == pyabc.UNSAT:
        return 'UNSAT'
    else:
        return 'UNKNOWN'

proof_command_wrapper_internal( bmcs_prooffunc, "HWMCC", "/bmcs_aiger", 0, multi=False, bmc_depth=True, write_cex=True)
