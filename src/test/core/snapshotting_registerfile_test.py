from pymtl import *
from util.test_utils import run_test_vector_sim
from util.rtl.snapshotting_registerfile import SnapshottingRegisterFile

pymtl_broken = True


def test_basic():
  run_test_vector_sim(
      SnapshottingRegisterFile( 8, 4, 1, 1, False, 1 ),
      [
          ( 'rd_addr[0] rd_data[0]* wr_addr[0] wr_data[0] wr_en[0] snapshot_port.call snapshot_port.ret.id* snapshot_port.ret.valid* restore_port.call restore_port.arg.id free_snapshot_port.call free_snapshot_port.arg.id'
          ),
          ( 0, 0, 0, 8, 1, 0, '?', '?', 0, 0, 0, 0 ),
          ( 0, 8, 2, 3, 1, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 3, 0, 0, 0, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 3, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0 ),  # allocate a snapshot
          ( 0, 8, 0, 7, 1, 0, '?', '?', 0, 0, 0, 0 ),
          ( 0, 7, 2, 4, 1, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 4, 0, 0, 0, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0 ),  # fail to allocate a snapshot
          ( 2, 4, 0, 0, 0, 0, '?', '?', 1, 0, 0, 0 ),  # restore the snapshot
          ( 0, 8, 2, 3, 1, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 3, 0, 0, 0, 0, '?', '?', 0, 0, 0, 0 ),
          ( 2, 3, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0 ),  # fail to allocate a snapshot
          ( 2, 3, 0, 0, 0, 0, '?', '?', 0, 0, 1, 0 ),  # free the snapshot
          ( 2, 3, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0 ),  # allocate a snapshot
      ],
      dump_vcd=None,
      test_verilog=not pymtl_broken )
