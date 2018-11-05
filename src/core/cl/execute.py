from pymtl import *
from msg.decode import *
from msg.issue import *
from msg.execute import *
from msg.control import *
from util.cl.ports import InValRdyCLPort, OutValRdyCLPort
from util.line_block import LineBlock
from copy import deepcopy


class ExecuteUnitCL( Model ):

  def __init__( s, dataflow, controlflow ):
    s.issued_q = InValRdyCLPort( IssuePacket() )
    s.result_q = OutValRdyCLPort( ExecutePacket() )

    s.dataflow = dataflow
    s.controlflow = controlflow

    s.done = Wire( 1 )

  def xtick( s ):
    if s.reset:
      s.done.next = 1
      return

    if s.result_q.full():
      return

    if s.done:
      if s.issued_q.empty():
        return
      s.current = s.issued_q.deq()

      s.work = ExecutePacket()
      copy_common_bundle( s.current, s.work )
      s.work.opcode = s.current.opcode
      copy_field_valid_pair( s.current, s.work, 'rd' )

    # verify instruction still alive
    creq = TagValidRequest()
    creq.tag = s.current.tag
    cresp = s.controlflow.tag_valid( creq )
    if not cresp.valid:
      # if we allocated a destination register for this instruction,
      # we must free it
      if s.current.rd_valid:
        s.dataflow.free_tag( s.current.rd )
      # retire instruction from controlflow
      creq = RetireRequest()
      creq.tag = s.current.tag
      s.controlflow.retire( creq )
      s.done.next = 1
      return

    if not s.work.valid:
      s.done.next = 1
      s.result_q.enq( s.work )
      return

    if s.current.inst == RV64Inst.LUI:
      s.work.result = sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.AUIPC:
      s.work.result = s.current.pc + sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.ADDI:
      s.work.result = s.current.rs1 + sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.SLTI:
      if s.current.rs1.int() < s.current.imm.int():
        s.work.result = 1
      else:
        s.work.result = 0
    elif s.current.inst == RV64Inst.SLTIU:
      if s.current.rs1.uint() < s.current.imm.uint():
        s.work.result = 1
      else:
        s.work.result = 0
    elif s.current.inst == RV64Inst.XORI:
      s.work.result = s.current.rs1 ^ sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.ORI:
      s.work.result = s.current.rs1 | sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.ANDI:
      s.work.result = s.current.rs1 & sext( s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.SLLI:
      s.work.result = s.current.rs1 << s.current.imm
    elif s.current.inst == RV64Inst.SRLI:
      s.work.result = Bits(
          XLEN, s.current.rs1.uint() >> s.current.imm.uint(), trunc=True )
    elif s.current.inst == RV64Inst.SRAI:
      s.work.result = Bits(
          XLEN, s.current.rs1.int() >> s.current.imm.uint(), trunc=True )
    # Register register insts
    elif s.current.inst == RV64Inst.ADD:
      s.work.result = s.current.rs1 + s.current.rs2
    elif s.current.inst == RV64Inst.SUB:
      s.work.result = s.current.rs1 - s.current.rs2
    elif s.current.inst == RV64Inst.SLL:
      s.work.result = Bits(
          XLEN, s.current.rs1 << s.current.rs2[:5 ], trunc=True )
    elif s.current.inst == RV64Inst.SRL:
      s.work.result = Bits(
          XLEN, s.current.rs1.uint() >> s.current.rs2[:5 ].uint(), trunc=True )
    elif s.current.inst == RV64Inst.SRA:
      s.work.result = Bits(
          XLEN, s.current.rs1.int() >> s.current.rs2[:5 ].uint(), trunc=True )
    elif s.current.inst == RV64Inst.SLT:
      s.work.result = int( s.current.rs1.int() < s.current.rs2.int() )
    elif s.current.inst == RV64Inst.SLTU:
      s.work.result = int( s.current.rs1.uint() < s.current.rs2.uint() )
    elif s.current.inst == RV64Inst.XOR:
      s.work.result = s.current.rs1 ^ s.current.rs2
    elif s.current.inst == RV64Inst.OR:
      s.work.result = s.current.rs1 | s.current.rs2
    elif s.current.inst == RV64Inst.AND:
      s.work.result = s.current.rs1 & s.current.rs2
    elif s.current.inst == RV64Inst.MUL:
      s.work.result = Bits(
          XLEN, s.current.rs1.int() * s.current.rs2.int(), trunc=True )
    elif s.current.inst == RV64Inst.MULH:
      s.work.result = Bits(
          XLEN, ( s.current.rs1.int() * s.current.rs2.int() ) >> XLEN,
          trunc=True )
    elif s.current.inst == RV64Inst.MULHU:
      s.work.result = Bits(
          XLEN, ( s.current.rs1.uint() * s.current.rs2.uint() ) >> XLEN,
          trunc=True )
    elif s.current.inst == RV64Inst.MULHSU:
      s.work.result = Bits(
          XLEN, ( s.current.rs1.int() * s.current.rs2.uint() ) >> XLEN,
          trunc=True )
    elif s.current.inst == RV64Inst.DIV:
      if ( s.current.rs2.int() == 0 ):
        s.work.result = sext( 1, XLEN )
      # Special overflow case
      elif ( s.current.rs1.int() == -2**( XLEN - 1 ) and
             s.current.rs2.int() == -1 ):
        s.work.result = s.current.rs1
      else:
        s.work.result = Bits(
            XLEN, s.current.rs1.int() // s.current.rs2.int(), trunc=True )
    elif s.current.inst == RV64Inst.DIVU:
      if ( s.current.rs2.int() == 0 ):
        s.work.result = sext( 1, XLEN )
      else:
        s.work.result = Bits(
            XLEN, s.current.rs1.uint() // s.current.rs2.uint(), trunc=True )
    elif s.current.inst == RV64Inst.REM:
      if ( s.current.rs2.int() == 0 ):
        s.work.result = s.current.rs1
      # Special overflow case
      elif ( s.current.rs1.int() == -2**( XLEN - 1 ) and
             s.current.rs2.int() == -1 ):
        s.work.result = 0
      else:
        s.work.result = Bits(
            XLEN, s.current.rs1.int() % s.current.rs2.int(), trunc=True )
    elif s.current.inst == RV64Inst.REMU:
      if ( s.current.rs2.int() == 0 ):
        s.work.result = s.current.rs1
      else:
        s.work.result = Bits(
            XLEN, s.current.rs1.uint() % s.current.rs2.uint(), trunc=True )
    # W suffix instructions
    elif s.current.inst == RV64Inst.MULW:
      s.work.result = sext( s.current.rs1[:32 ] * s.current.rs2[:32 ], XLEN )
    elif s.current.inst == RV64Inst.DIVW:
      s1 = s.current.rs1[:32 ].int()
      s2 = s.current.rs2[:32 ].int()
      if ( s2 == 0 ):
        s.work.result = sext( 1, XLEN )
      # Special overflow case
      elif ( s1 == -2**( 32 - 1 ) and s2 == -1 ):
        s.work.result = sext( s1, XLEN )
      else:
        s.work.result = sext( s1 // s2, XLEN )
    elif s.current.inst == RV64Inst.DIVUW:
      s1 = s.current.rs1[:32 ].uint()
      s2 = s.current.rs2[:32 ].uint()
      if ( s2 == 0 ):
        s.work.result = sext( 1, XLEN )
      else:
        s.work.result = sext( s1 // s2, XLEN )
    elif s.current.inst == RV64Inst.REMW:
      s1 = s.current.rs1[:32 ].int()
      s2 = s.current.rs2[:32 ].int()

      if ( s2 == 0 ):
        s.work.result = s1
      # Special overflow case
      elif ( s1 == -2**( 32 - 1 ) and s2 == -1 ):
        s.work.result = 0
      else:
        s.work.result = sext( s1 % s2, XLEN )
    elif s.current.inst == RV64Inst.REMU:
      s1 = s.current.rs1[:32 ].uint()
      s2 = s.current.rs2[:32 ].uint()
      if ( s1 == 0 ):
        s.work.result = s1
      else:
        s.work.result = sext( s1 % s2, XLEN )
    elif s.current.inst == RV64Inst.ADDW:
      s.work.result = sext( s.current.rs1[:32 ] + s.current.rs2[:32 ], XLEN )
    elif s.current.inst == RV64Inst.SUBW:
      s.work.result = sext( s.current.rs1[:32 ] - s.current.rs2[:32 ], XLEN )
    elif s.current.inst == RV64Inst.SLLW:
      s.work.result = sext( s.current.rs1[:32 ] << s.current.rs2[:5 ].uint(),
                            XLEN )
    elif s.current.inst == RV64Inst.SRLW:
      s.work.result = sext( s.current.rs1[:32 ] >> s.current.rs2[:5 ].uint(),
                            XLEN )
    elif s.current.inst == RV64Inst.SRAW:
      s.work.result = Bits(
          XLEN,
          s.current.rs1[:32 ].int() >> s.current.rs2[:5 ].uint(),
          trunc=True )
    elif s.current.inst == RV64Inst.ADDIW:
      s.work.result = sext( s.current.rs1[:32 ] + s.current.imm[:32 ], XLEN )
    elif s.current.inst == RV64Inst.SLLIW:
      s.work.result = sext( s.current.rs1[:32 ] << s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.SRLIW:
      s.work.result = sext( s.current.rs1[:32 ] >> s.current.imm, XLEN )
    elif s.current.inst == RV64Inst.SRAIW:
      s.work.result = Bits(
          XLEN, s.current.rs1[:32 ].int() >> s.current.imm.uint(), trunc=True )
    elif s.current.is_control_flow:
      taken = False
      base = s.current.pc
      if s.current.inst == RV64Inst.BEQ:
        taken = s.current.rs1 == s.current.rs2
      elif s.current.inst == RV64Inst.BNE:
        taken = s.current.rs1 != s.current.rs2
      elif s.current.inst == RV64Inst.BLT:
        taken = s.current.rs1.int() < s.current.rs2.int()
      elif s.current.inst == RV64Inst.BGE:
        taken = s.current.rs1.int() >= s.current.rs2.int()
      elif s.current.inst == RV64Inst.BLTU:
        taken = s.current.rs1.uint() < s.current.rs2.uint()
      elif s.current.inst == RV64Inst.BGEU:
        taken = s.current.rs1.uint() >= s.current.rs2.uint()
      elif s.current.inst == RV64Inst.JAL:
        s.work.result = s.current.pc + ILEN_BYTES
        taken = True
      elif s.current.inst == RV64Inst.JALR:
        s.work.result = s.current.pc + ILEN_BYTES
        taken = True
        base = s.current.rs1
      else:
        assert False, "invalid branch: {}".format(
            RV64Inst.name( s.current.inst ) )

      if taken:
        target_pc = base + sext( s.current.imm, XLEN )

        # if JALR force last bit to 0
        target_pc[ 0 ] = 0
      else:
        target_pc = s.current.pc + ILEN_BYTES
      # note that we request a redirect no matter which way the branch went
      # this is because who knows how the branch was predicted
      # the control flow unit maintains information about which way
      # the flow of instructions behind the branch went, and will do nothing
      # if predicted correctly
      creq = RedirectRequest()
      creq.source_tag = s.current.tag
      creq.target_pc = target_pc
      creq.at_commit = 0
      s.controlflow.request_redirect( creq )

    elif s.current.inst == RV64Inst.CSRRW:
      if s.current.rd_valid:
        temp, worked = s.dataflow.read_csr( s.current.csr )
      if not worked:
        s.done.next = 0
        return
      s.work.result = temp
      s.dataflow.write_csr( s.current.csr, s.current.rs1 )
    elif s.current.inst == RV64Inst.CSRRS:
      temp, worked = s.dataflow.read_csr( s.current.csr )
      if not worked:
        s.done.next = 0
        return
      s.work.result = temp
      # TODO: not quite right because we should attempt to set
      # if the value of rs1 is zero but rs1 is not x0
      if s.current.rs1 != 0:
        s.dataflow.write_csr( s.current.csr, s.work.result | s.current.rs1 )
    else:
      raise NotImplementedError( 'Not implemented so sad: ' +
                                 RV64Inst.name( s.current.inst ) )

    s.done.next = 1
    s.result_q.enq( s.work )

  def line_trace( s ):
    return LineBlock([
        "{}".format( s.result_q.msg().tag ),
        "{: <8} rd({}): {}".format(
            RV64Inst.name( s.result_q.msg().inst ),
            s.result_q.msg().rd_valid,
            s.result_q.msg().rd ),
        "res: {}".format( s.result_q.msg().result ),
    ] ).validate( s.result_q.val() )