#
import  logging;
import  TRACE, os
import  midas, midas.client

import tfm.rc.control.farm_manager as farm_manager
import tfm.rc.control.artdaq       as artdaq

logger = logging.getLogger('test_001')
logger.info("Initializing %s" % "get_next_run")
client = midas.client.MidasClient("test_001", None, "tracker", None)

#------------------------------------------------------------------------------
def test_001(config_name):
    TRACE.INFO(f'-- START');
    artdaq_config_dir = os.path.expandvars(client.odb_get("/Mu2e/ConfigDir")) + '/artdaq'

    os.environ["TFM_SETUP_FHICLCPP"] = f"{artdaq_config_dir}/.setup_fhiclcpp"

    
    fm   = farm_manager.FarmManager(odb_client        = client,
                                    artdaq_config_dir = artdaq_config_dir,
                                    rpc_host          = 'mu2e-dl-01');
    p = fm.find_process("eb06")
    p.lastreturned = p.server.daq.init(p.fhicl_used, 60)       ## timeout=60

    TRACE.INFO(f'-- END: p.lastreturned:{p.lastreturned}');

#------------------------------------------------------------------------------
# not yet decided
#------------------------------------------------------------------------------
def test_002(config_name):
    TRACE.INFO(f'-- START');
    artdaq_config_dir = os.path.expandvars(client.odb_get("/Mu2e/ConfigDir")) + '/artdaq'

    os.environ["TFM_SETUP_FHICLCPP"] = f"{artdaq_config_dir}/.setup_fhiclcpp"

    
    fm   = farm_manager.FarmManager(odb_client        = client,
                                    artdaq_config_dir = artdaq_config_dir,
                                    rpc_host          = 'mu2e-dl-01');
    p = fm.find_process("eb06")
    p.lastreturned = p.server.daq.init(p.fhicl_used, 60)       ## timeout=60

    TRACE.INFO(f'-- END: p.lastreturned:{p.lastreturned}');
    
#------------------------------------------------------------------------------
if __name__ == "__main__":

#    test1()
#    test2_set_thresholds(25,'MN261')
    test_001("demo_mc2");
