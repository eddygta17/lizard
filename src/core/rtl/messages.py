from pymtl import *
from config.general import *

class PipelineMsg(BitStructDefinition):
  def __init__(s):
    # TODO: This is far too expensive to keep arround
    # in every pipeline stage
    # maybe lift to a global register and arbitrate
    # based on sequence number
    s.trap = BitField(1)
    s.mcause = BitField(XLEN)
    s.mtval = BitField(XLEN)
    s.pc = BitField(XLEN)


class FetchMsg(PipelineMsg):
  def __init__(s):
    super(FrontEndMsg, s).__init__(s)
    s.inst = BitField(ILEN)


class DecodeMsg(PipelineMsg):
  def _init__(s):
    super(DecodeMsg, s).__init__(s)
    s.src0_val = BitField(1)
    s.src0 = BitField(AREG_IDX_NBITS)
    s.src1_val = BitField(1)
    s.src1 = BitField(AREG_IDX_NBITS)
    s.dest_val = BitField(1)
    s.dest = BitField(AREG_IDX_NBITS)
