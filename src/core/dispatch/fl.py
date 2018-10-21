from pymtl import *
from msg import MemMsg4B
from msg.fetch import FetchPacket
from msg.decode import *
from msg.control import *
from pclib.ifcs import InValRdyBundle, OutValRdyBundle
from util.cl.adapters import UnbufferedInValRdyQueueAdapter, UnbufferedOutValRdyQueueAdapter
from config.general import *
from util.line_block import LineBlock
from copy import deepcopy


class DispatchFL( Model ):

  def __init__( s, controlflow ):
    s.instr = InValRdyBundle( FetchPacket() )
    s.decoded = OutValRdyBundle( DecodePacket() )

    s.instr_q = UnbufferedInValRdyQueueAdapter( s.instr )
    s.decoded_q = UnbufferedOutValRdyQueueAdapter( s.decoded )

    s.out = Wire( DecodePacket() )
    s.out_valid = Wire( 1 )

    s.controlflow = controlflow

  def xtick( s ):
    s.instr_q.xtick()
    s.decoded_q.xtick()

    if s.reset:
      s.out_valid.next = 0
      return

    if s.out_valid.value:
      if not s.decoded_q.full():
        s.decoded_q.enq( deepcopy( s.out ) )
        s.out_valid.next = 0
      else:
        return

    if s.instr_q.empty():
      return

    decoded = s.instr_q.deq()

    # verify instruction still alive
    creq = TagValidRequest()
    creq.tag = decoded.tag
    cresp = s.controlflow.tag_valid( creq )
    if not cresp.valid:
      return

    inst = decoded.instr
    # Decode it and create packet
    opmap = {
        int( Opcode.OP_IMM ): s.dec_op_imm,
        int( Opcode.OP ): s.dec_op,
        int( Opcode.SYSTEM ): s.dec_system,
        int( Opcode.BRANCH ): s.dec_branch,
        int( Opcode.JAL ): s.dec_jal,
        int( Opcode.JALR ): s.dec_jalr,
    }
    try:
      opcode = inst[ RVInstMask.OPCODE ]
      s.out.next = opmap[ opcode.uint() ]( inst )
      s.out.next.pc = decoded.pc
      s.out.next.tag = decoded.tag
    except KeyError:
      return
      # TODO: illegal instruction exception
      #raise NotImplementedError( 'Not implemented so sad: ' +
      #                           Opcode.name( opcode ) )
    s.out_valid.next = 1

  def dec_op_imm( s, inst ):
    res = DecodePacket()
    res.rs1 = inst[ RVInstMask.RS1 ]
    res.rs1_valid = 1
    res.rs2_valid = 0
    res.rd = inst[ RVInstMask.RD ]
    res.rd_valid = 1
    # Mapping from func3 to map of func7 to shamt instruction
    shamts = {
        0b001: {
            0b0000000: RV64Inst.SLLI,
        },
        0b101: {
            0b0000000: RV64Inst.SRLI,
            0b0100000: RV64Inst.SRAI,
        },
    }

    nshamts = {
        0b000: RV64Inst.ADDI,
        0b010: RV64Inst.SLTI,
        0b011: RV64Inst.SLTIU,
        0b100: RV64Inst.XORI,
        0b110: RV64Inst.ORI,
        0b111: RV64Inst.ANDI,
    }
    func3 = inst[ RVInstMask.FUNCT3 ].uint()
    func7 = inst[ RVInstMask.FUNCT7 ].uint()
    if ( inst[ RVInstMask.FUNCT3 ].uint() in shamts ):
      res.inst = shamts[ func3 ][ func7 ]
      res.imm = zext( inst[ RVInstMask.SHAMT ], DECODED_IMM_LEN )
    else:
      res.inst = nshamts[ func3 ]
      res.imm = sext( inst[ RVInstMask.I_IMM ], DECODED_IMM_LEN )

    return res

  def dec_op( s, inst ):
    res = DecodePacket()
    res.rs1 = inst[ RVInstMask.RS1 ]
    res.rs2 = inst[ RVInstMask.RS2 ]
    res.rd = inst[ RVInstMask.RD ]
    res.imm = 0
    res.rs1_valid = 1
    res.rs2_valid = 1
    res.rd_valid = 1

    func3 = int( inst[ RVInstMask.FUNCT3 ] )
    func7 = int( inst[ RVInstMask.FUNCT7 ] )
    insts = {
        ( 0b000, 0b0000000 ): RV64Inst.ADD,
        ( 0b000, 0b0100000 ): RV64Inst.SUB,
        ( 0b001, 0b0000000 ): RV64Inst.SLL,
        ( 0b010, 0b0000000 ): RV64Inst.SLT,
        ( 0b011, 0b0000000 ): RV64Inst.SLTU,
        ( 0b100, 0b0000000 ): RV64Inst.XOR,
        ( 0b101, 0b0000000 ): RV64Inst.SRL,
        ( 0b101, 0b0100000 ): RV64Inst.SRA,
        ( 0b110, 0b0000000 ): RV64Inst.OR,
        ( 0b111, 0b0000000 ): RV64Inst.AND,
    }
    res.inst = insts[( func3, func7 ) ]

    return res

  def dec_system( s, inst ):
    res = DecodePacket()

    func3 = int( inst[ RVInstMask.FUNCT3 ] )
    insts = {
        0b001: RV64Inst.CSRRW,
        0b010: RV64Inst.CSRRS,
        0b011: RV64Inst.CSRRC,
    }

    res.inst = insts[ func3 ]
    res.rs1 = inst[ RVInstMask.RS1 ]
    res.rs1_valid = 1
    res.rs2_vallid = 0
    res.rd = inst[ RVInstMask.RD ]
    res.rd_valid = 1

    res.csr = inst[ RVInstMask.CSRNUM ]
    res.csr_valid = 1

    return res

  def dec_branch( s, inst ):
    res = DecodePacket()
    func3 = int( inst[ RVInstMask.FUNCT3 ] )
    insts = {
        0b000: RV64Inst.BEQ,
        0b001: RV64Inst.BNE,
        0b100: RV64Inst.BLT,
        0b101: RV64Inst.BGE,
        0b110: RV64Inst.BLTU,
        0b111: RV64Inst.BGEU,
    }

    res.inst = insts[ func3 ]

    res.rs1 = inst[ RVInstMask.RS1 ]
    res.rs1_valid = 1
    res.rs2 = inst[ RVInstMask.RS2 ]
    res.rs2_valid = 1
    res.rd_valid = 0

    imm = concat( inst[ RVInstMask.B_IMM3 ], inst[ RVInstMask.B_IMM2 ],
                  inst[ RVInstMask.B_IMM1 ], inst[ RVInstMask.B_IMM0 ],
                  Bits( 1, 0 ) )
    res.imm = sext( imm, DECODED_IMM_LEN )
    res.is_branch = 1

    return res

  def dec_jal( s, inst ):
    res = DecodePacket()

    res.inst = RV64Inst.JAL
    res.rd = inst[ RVInstMask.RD ]
    res.rd_valid = 1
    imm = concat( inst[ RVInstMask.J_IMM3 ], inst[ RVInstMask.J_IMM2 ],
                  inst[ RVInstMask.J_IMM1 ], inst[ RVInstMask.J_IMM0 ],
                  Bits( 1, 0 ) )
    res.imm = sext( imm, DECODED_IMM_LEN )
    res.is_branch = 1

    return res

  def dec_jalr( s, inst ):
    res = DecodePacket()

    res.inst = RV64Inst.JALR
    res.rs1 = inst[ RVInstMask.RS1 ]
    res.rs1_valid = 1
    res.rd = inst[ RVInstMask.RD ]
    res.rd_valid = 1
    imm = inst[ RVInstMask.I_IMM ]
    res.imm = sext( imm, DECODED_IMM_LEN )
    res.is_branch = 1

    return res

  def line_trace( s ):
    return LineBlock([
        "{}".format( s.out.tag ), "{}".format( s.out.pc ),
        "{: <8} rd({}): {}".format(
            RV64Inst.name( s.out.inst ), s.out.rd_valid,
            s.out.rd ), "imm: {}".format( s.out.imm ), "rs1({}): {}".format(
                s.out.rs1_valid, s.out.rs1 ), "rs2({}): {}".format(
                    s.out.rs2_valid, s.out.rs2 )
    ] ).validate( s.out_valid )
