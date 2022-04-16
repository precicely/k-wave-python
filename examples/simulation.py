import numpy as np
import scipy.io

from tests import setup_test
from tempfile import gettempdir
from kwave.kspaceFirstOrder3D import kspaceFirstOrder3DC
from kwave.ktransducer import *
from tests.diff_utils import compare_against_ref
from kwave.kmedium import kWaveMedium


def prepare_simulations(return_variables_only=False):
    # pathname for the input and output files
    # pathname = gettempdir()
    pathname = '/Users/faridyagubbayli/Work/k-wave.py/tmp_dir/input'

    # simulation settings
    DATA_CAST = 'single'
    RUN_SIMULATION = True

    # =========================================================================
    # DEFINE THE K-WAVE GRID
    # =========================================================================

    # set the size of the perfectly matched layer (PML)
    PML_X_SIZE = 20            # [grid points]
    PML_Y_SIZE = 10            # [grid points]
    PML_Z_SIZE = 10            # [grid points]

    # set total number of grid points not including the PML
    Nx = 256 - 2*PML_X_SIZE    # [grid points]
    Ny = 128 - 2*PML_Y_SIZE    # [grid points]
    Nz = 128 - 2*PML_Z_SIZE     # [grid points]

    # set desired grid size in the x-direction not including the PML
    x = 40e-3                  # [m]

    # calculate the spacing between the grid points
    dx = x/Nx                  # [m]
    dy = dx                    # [m]
    dz = dx                    # [m]

    # create the k-space grid
    kgrid = kWaveGrid([Nx, Ny, Nz], [dx, dy, dz])

    # =========================================================================
    # DEFINE THE MEDIUM PARAMETERS
    # =========================================================================

    # define the properties of the propagation medium
    c0 = 1540
    rho0 = 1000

    medium = kWaveMedium(
        sound_speed=None,  # will be set later
        alpha_coeff=0.75,
        alpha_power=1.5,
        BonA=6
    )

    # create the time array
    t_end = (Nx * dx) * 2.2 / c0   # [s]
    kgrid.makeTime(c0, t_end=t_end)

    # =========================================================================
    # DEFINE THE INPUT SIGNAL
    # =========================================================================

    # define properties of the input signal
    source_strength = 1e6          # [Pa]
    tone_burst_freq = 1.5e6        # [Hz]
    tone_burst_cycles = 4

    # create the input signal using toneBurst
    input_signal = toneBurst(1/kgrid.dt, tone_burst_freq, tone_burst_cycles)

    # scale the source magnitude by the source_strength divided by the
    # impedance (the source is assigned to the particle velocity)
    input_signal = (source_strength / (c0 * rho0)) * input_signal

    # =========================================================================
    # DEFINE THE ULTRASOUND TRANSDUCER
    # =========================================================================

    # physical properties of the transducer
    transducer = dotdict()
    transducer.number_elements = 32    # total number of transducer elements
    transducer.element_width = 2       # width of each element [grid points/voxels]
    transducer.element_length = 24     # length of each element [grid points/voxels]
    transducer.element_spacing = 0     # spacing (kerf  width) between the elements [grid points/voxels]
    transducer.radius = float('inf')   # radius of curvature of the transducer [m]

    # calculate the width of the transducer in grid points
    transducer_width = transducer.number_elements * transducer.element_width + (transducer.number_elements - 1) * transducer.element_spacing

    # use this to position the transducer in the middle of the computational grid
    transducer.position = np.round([1, Ny/2 - transducer_width/2, Nz/2 - transducer.element_length/2])

    # properties used to derive the beamforming delays
    not_transducer = dotdict()
    not_transducer.sound_speed = c0                    # sound speed [m/s]
    not_transducer.focus_distance = 20e-3              # focus distance [m]
    not_transducer.elevation_focus_distance = 19e-3    # focus distance in the elevation plane [m]
    not_transducer.steering_angle = 0                  # steering angle [degrees]

    # apodization
    not_transducer.transmit_apodization = 'Hanning'
    not_transducer.receive_apodization = 'Rectangular'

    # define the transducer elements that are currently active
    not_transducer.active_elements = np.ones((transducer.number_elements, 1))

    # append input signal used to drive the transducer
    not_transducer.input_signal = input_signal

    # create the transducer using the defined settings
    transducer = kWaveTransducerSimple(kgrid, **transducer)
    not_transducer = NotATransducer(transducer, kgrid, **not_transducer)

    if return_variables_only:
        return not_transducer

    # =========================================================================
    # DEFINE THE MEDIUM PROPERTIES
    # =========================================================================
    # define a large image size to move across
    number_scan_lines = 96

    work_project_dir = '/Users/faridyagubbayli/Work'
    phantom_path = os.path.join(work_project_dir, 'pumba_linux/november/18_19_nov/phantom_data.mat')
    phantom = scipy.io.loadmat(phantom_path)
    sound_speed_map     = phantom['sound_speed_map']
    density_map         = phantom['density_map']

    # =========================================================================
    # RUN THE SIMULATION
    # =========================================================================

    # preallocate the storage
    simulation_data = []

    # run the simulation if set to true, otherwise, load previous results from disk
    if RUN_SIMULATION:

        # set medium position
        medium_position = 0

        # loop through the scan lines
        for scan_line_index in range(1, number_scan_lines + 1):
        # for scan_line_index in range(1, 10):
            # update the command line status
            print(f'Computing scan line {scan_line_index} of {number_scan_lines}')

            # load the current section of the medium
            medium.sound_speed = sound_speed_map[:, medium_position:medium_position + Ny, :]
            medium.density = density_map[:, medium_position:medium_position + Ny, :]

            # set the input settings
            input_filename  = f'example_input_{scan_line_index}.h5'
            input_file_full_path = os.path.join(pathname, input_filename)
            # set the input settings
            input_args = {
                'PMLInside': False,
                'PMLSize': [PML_X_SIZE, PML_Y_SIZE, PML_Z_SIZE],
                'DataCast': DATA_CAST,
                'DataRecast': True,
                'SaveToDisk': input_file_full_path
            }

            # run the simulation
            kspaceFirstOrder3DC(**{
                'medium': medium,
                'kgrid': kgrid,
                'source': not_transducer,
                'sensor': not_transducer,
                **input_args
            })

            # update medium position
            medium_position = medium_position + transducer.element_width

    else:
        raise NotImplementedError
    

def run_simulations():
    binary_path = '/data/code/Work/k-wave-toolbox-version-1.3/k-Wave/binaries/'
    system_string = 'OMP_PLACES=cores;  OMP_PROC_BIND=SPREAD; '
    # binary_name = 'kspaceFirstOrder-CUDA'
    binary_name = 'kspaceFirstOrder-OMP'
    options_string = ' --p_raw'
    for i in range(1, 97):
        input_filename = f'/data/tmp_sim_data/example_input_{i}.h5'
        output_filename = f'/data/tmp_sim_data/example_output_{i}.h5'

        command = f'export LD_LIBRARY_PATH=; {system_string} cd {binary_path}; ' \
                  f'./{binary_name} -i {input_filename} -o {output_filename} {options_string}'

        print(command)
        # os.system(command)
        break


def load_simulations():
    not_transducer = prepare_simulations(True)
    simulation_data = []
    for i in range(1, 97):
        print(i)
        root_path = 'tmp_dir/output'
        output_filename = os.path.join(root_path, f'example_output_{i}.h5')

        with h5py.File(output_filename, 'r') as hf:
            sensor_data = np.array(hf['p'])[0].T
            sensor_data = not_transducer.combine_sensor_data(sensor_data)
            simulation_data.append(sensor_data)

    simulation_data = np.stack(simulation_data, axis=0)
    scipy.io.savemat('../sensor_data_py.mat', {'sensor_data_all_lines': simulation_data})
#
# prepare_simulations()
# run_simulations()
load_simulations()
