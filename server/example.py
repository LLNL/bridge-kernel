# Copyright 2019 Lawrence Livermore National Security, LLC and other
# Bridge Kernel Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from mpi4py import MPI
import time

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from mpi_server import MPIServer

# these will be available in global ns
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
greeting = "hi there"
foo = 4


# demonstriate streaming output
def bar(n=10):
    for i in range(n):
        print(i)
        time.sleep(1)


def ranksum():
    return comm.allreduce(rank, MPI.SUM)


# demo image
def show_png_url(url="https://www.llnl.gov/sites/all/themes/llnl_bootstrap/logo.png"):
    image(urlopen(url).read(), "png") # noqa


# demo mpi_print
def hello_from_all():
    mpi_print("hello from %d" % rank) # noqa


server = MPIServer(comm=comm, ns=globals())
server.serve()
if server.wait_for_client():
    server.loop()
server.stop()
