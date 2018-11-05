import struct
import inspect

from pymtl import *

from pclib.test import TestSource, TestSink
from pclib.test import TestMemory

from util.tinyrv2_encoding import DATA_PACK_DIRECTIVE

from core.fl.proc import ProcFL

from config.general import *
from msg.mem import MemMsg4B
from util import line_block
from util.line_block import Divider


class ProcTestHarnessFL( Model ):

  def __init__( s ):

    s.src = TestSource( XLEN, [], 0 )
    s.sink = TestSink( XLEN, [], 0 )
    s.proc = ProcFL()
    s.mem = TestMemory( MemMsg4B, 2, 0, 0 )

    s.connect( s.proc.mngr2proc, s.src.out )
    s.connect( s.proc.proc2mngr, s.sink.in_ )

    s.connect( s.proc.imemreq, s.mem.reqs[ 0 ] )
    s.connect( s.proc.imemresp, s.mem.resps[ 0 ] )
    s.connect( s.proc.dmemreq, s.mem.reqs[ 1 ] )
    s.connect( s.proc.dmemresp, s.mem.resps[ 1 ] )

    # Starting F16 we turn core_id into input ports to
    # enable module reusability. In the past it was passed as arguments.
    s.connect( s.proc.core_id, 0 )

  def load( self, mem_image ):
    sections = mem_image.get_sections()
    for section in sections:
      # For .mngr2proc sections, copy section into mngr2proc src
      if section.name == ".mngr2proc":
        for i in xrange( 0, len( section.data ), XLEN_BYTES ):
          bits = struct.unpack_from( DATA_PACK_DIRECTIVE,
                                     buffer( section.data, i,
                                             XLEN_BYTES ) )[ 0 ]
          self.src.src.msgs.append( Bits( XLEN, bits ) )
      # For .proc2mngr sections, copy section into proc2mngr_ref src
      elif section.name == ".proc2mngr":
        for i in xrange( 0, len( section.data ), XLEN_BYTES ):
          bits = struct.unpack_from( DATA_PACK_DIRECTIVE,
                                     buffer( section.data, i,
                                             XLEN_BYTES ) )[ 0 ]
          self.sink.sink.msgs.append( Bits( XLEN, bits ) )
      # For all other sections, simply copy them into the memory
      else:
        start_addr = section.addr
        stop_addr = section.addr + len( section.data )
        self.mem.mem[ start_addr:stop_addr ] = section.data

  def cleanup( s ):
    del s.mem.mem[: ]

  def done( s ):
    return s.src.done and s.sink.done

  def line_trace( s ):
    return "fl test who needs a line trace"