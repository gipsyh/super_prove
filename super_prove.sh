#!/bin/sh

abc_root()
{
    cwd="$(pwd)"
    cd $(dirname "$1")
    echo $(dirname "$(pwd)")
    cd "${cwd}"
}

abc_dir=$(abc_root "$0")
bin_dir="${abc_dir}"/bin

export CONDA_PREFIX=/usr/local/miniconda3/envs/py2
export LIBRARY_PATH=$CONDA_PREFIX/lib:$LIBRARY_PATH                                
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
export PYTHONPATH=$CONDA_PREFIX/lib/python2.7/site-packages/ && PYTHONHOME=$CONDA_PREFIX/

exec ${bin_dir}/abc -q "/super_prove_aiger $*"
