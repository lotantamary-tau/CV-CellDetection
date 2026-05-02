
#!/usr/bin/env python3
"""
CNMF Manager Runner Script

This script provides a flexible interface to run CNMF with different parameter configurations,
initialization methods, and analysis options. It allows easy switching between:
- greedy_roi vs corr_pnr initialization
- Different parameter sets
- Debug tracking options
- Visualization options

Usage:
    python cnmf_manager.py --config greedy_roi_config
    python cnmf_manager.py --config corr_pnr_config --debug --visualize
"""

import argparse
import json
import os
import sys
import time
import tempfile
from pathlib import Path
import numpy as np
import tifffile

# Ensure sibling modules are importable when this file is run as a script.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# NOTE: the CNMF class import is deferred to run_cnmf() to keep
# importing cnmf_manager cheap (the instrumented_cnmf module imports
# many caiman submodules transitively).


class CNMFManager:
    """
    Manager class for running CNMF with different configurations
    """
    
    def __init__(self):
        self.configs = self._load_default_configs()
        self.results_dir = Path("./cnmf_results")
        self.results_dir.mkdir(exist_ok=True)
        
    def _load_default_configs(self):
        """Load default parameter configurations"""
        return {
            'greedy_roi_config': {
                'name': 'Greedy ROI Initialization',
                'description': 'Fast greedy ROI detection method',
                'params': {
                    # Data parameters
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 30,                    # frame rate
                    'decay_time': 0.4,           # length of a typical transient in seconds
                    
                    # Motion correction parameters
                    'motion_correct': True,
                    'pw_rigid': False,           # flag to select rigid vs pw_rigid motion correction
                    'max_shifts': (5, 5),        # maximum allowed rigid shift
                    'strides': (48, 48),         # start a new patch for pw-rigid motion correction every x pixels
                    'overlaps': (24, 24),        # overlap between patches (size of patch strides+overlaps)
                    'max_deviation_rigid': 3,    # maximum deviation allowed for patch with respect to rigid shifts
                    'border_nan': 'copy',        # replicate values along the borders
                    
                    # Parameters for source extraction and deconvolution
                    'p': 1,                      # order of the autoregressive system
                    'gnb': 2,                    # number of global background components
                    'merge_thr': 0.85,           # merging threshold, max correlation allowed
                    'rf': 40,                    # half-size of the patches in pixels
                    'stride_cnmf': 20,           # amount of overlap between the patches in pixels
                    'K': 4,                      # upper bound on number of components per patch
                    'gSig': [4, 4],              # expected half size of neurons in pixels
                    'method_init': 'greedy_roi', # initialization method
                    'ssub': 1,                   # spatial subsampling during initialization
                    'tsub': 1,                   # temporal subsampling during intialization
                    
                    # Parameters for component evaluation
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 30,
                        'nb': 2,
                        'rf': 40,
                        'K': 4, 
                        'gSig': [4, 4],
                        'stride': 20,
                        'method_init': 'greedy_roi',
                        'rolling_sum': True,
                        'merge_thr': 0.85,
                        'n_processes': 4,
                        'only_init': False,
                        'ssub': 1,
                        'tsub': 1,
                        'use_cnn': True              # Use CNN for component classification
                    }
                }
            },
            
            'corr_pnr_config': {
                'name': 'Correlation PNR Initialization',
                'description': 'Correlation and peak-to-noise ratio based initialization',
                'params': {
                    # Data parameters
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 30,
                    'decay_time': 0.4,
                    
                    # Motion correction parameters
                    'motion_correct': True,
                    'pw_rigid': False,
                    'max_shifts': (5, 5),
                    'strides': (48, 48),
                    'overlaps': (24, 24),
                    'max_deviation_rigid': 3,
                    'border_nan': 'copy',
                    
                    # Parameters for source extraction and deconvolution
                    'p': 1,
                    'gnb': 1,                    # Reduced background components to avoid broadcasting error
                    'merge_thr': 0.85,
                    'rf': 64,                    # Larger patches (64x64) more likely to have background
                    'stride_cnmf': 32,           # 50% overlap between patches
                    'K': 400,                     # Expected number of components
                    'gSig': [4, 4],
                    'method_init': 'corr_pnr',   # Use correlation PNR method
                    'ssub': 1,
                    'tsub': 1,
                    
                    # Correlation PNR specific parameters
                    'min_corr': 0.75,            # minimum local correlation for a seeding pixel
                    'min_pnr': 10,               # minimum peak-to-noise-ratio for a seeding pixel
                    'ring_size_factor': 1.4,     # radius of ring is gSig*ring_size_factor
                    'center_psf': True,          # whether to use 1p data
                    'ssub_B': 2,                 # additional downsampling factor in space for background
                    'init_iter': 2,              # number of iterations for initialization
                    
                    # Parameters for component evaluation
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 30,
                        'nb': 1,                 # Reduced background components
                        'rf': 64,                # Larger patches
                        'K': 400,
                        'gSig': [4, 4],
                        'stride': 32,            # Updated patch overlap for larger patches
                        'method_init': 'corr_pnr',
                        'rolling_sum': True,
                        'merge_thr': 0.85,
                        'n_processes': 4,
                        'only_init': False,
                        'ssub': 1,
                        'tsub': 1,
                        'min_corr': 0.75,
                        'min_pnr': 10,
                        'ring_size_factor': 1.4,
                        'center_psf': True,
                        'ssub_B': 2,
                        'init_iter': 2,
                        'use_cnn': True              # Use CNN for component classification
                    }
                }
            },
            
            'corr_pnr_no_patches_config': {
                'name': 'Correlation PNR No Patches (Optimized for Your Data)',
                'description': 'Correlation PNR with your proven parameters - global background handling',
                'params': {
                    # Data parameters - YOUR PROVEN VALUES
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 1.08,                  # YOUR frame rate
                    'decay_time': 20,            # YOUR decay time
                    'dxy': (1.243, 1.243),      # YOUR spatial resolution
                    
                    # Motion correction parameters
                    'motion_correct': True,
                    'pw_rigid': False,
                    'max_shifts': (5, 5),
                    'strides': (48, 48),
                    'overlaps': (24, 24),
                    'max_deviation_rigid': 3,
                    'border_nan': 'copy',
                    
                    # Parameters for source extraction and deconvolution - YOUR PROVEN VALUES
                    'p': 2,                      # YOUR autoregressive order
                    'gnb': 2,                    # Global background components
                    'merge_thr': 0.2,            # YOUR merge threshold
                    'rf': None,                  # No patches - global processing
                    'stride_cnmf': None,         # No patches
                    'K': 400,                    # Expected number of components (increased for global)
                    'gSig': [4, 4],              # Calculated as 0.5*d_px = 0.5*8 = 4
                    'method_init': 'corr_pnr',   # Use correlation PNR method
                    'ssub': 1,
                    'tsub': 1,
                    'bas_nonneg': True,          # YOUR setting
                    
                    # Correlation PNR specific parameters - need to tune for your data
                    'min_corr': 0.75,            # minimum local correlation for a seeding pixel
                    'min_pnr': 10,               # minimum peak-to-noise-ratio for a seeding pixel
                    'ring_size_factor': 1.4,     # radius of ring is gSig*ring_size_factor
                    'center_psf': True,          # whether to use 1p data
                    'ssub_B': 2,                 # additional downsampling factor in space for background
                    'init_iter': 2,              # number of iterations for initialization
                    
                    # Component evaluation - YOUR PROVEN VALUES
                    'min_SNR': 2.0,              # YOUR min SNR
                    'rval_thr': 0.85,            # YOUR space correlation threshold
                    'min_cnn_thr': 0.99,         # YOUR CNN threshold
                    'cnn_lowest': 0.1,           # YOUR CNN lowest threshold
                    
                    # Parameters for component evaluation
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 1.08,               # YOUR frame rate
                        'decay_time': 20,         # YOUR decay time
                        'nb': 2,                  # Global background components
                        'rf': None,               # No patches
                        'K': 400,
                        'gSig': [4, 4],           # Calculated: 0.5*d_px = 0.5*8 = 4
                        'stride': None,           # No patches
                        'method_init': 'corr_pnr',
                        'rolling_sum': True,
                        'merge_thr': 0.2,         # YOUR merge threshold
                        'n_processes': 4,
                        'only_init': False,       # Changed from your True to get full pipeline
                        'ssub': 1,
                        'tsub': 1,
                        'p': 2,                   # YOUR autoregressive order
                        'bas_nonneg': True,       # YOUR setting
                        'min_SNR': 2.0,           # YOUR min SNR
                        'rval_thr': 0.85,         # YOUR rval threshold
                        'use_cnn': True,          # Use CNN for component classification
                        'min_cnn_thr': 0.99,     # YOUR CNN threshold
                        'cnn_lowest': 0.1,        # YOUR CNN lowest threshold
                        'min_corr': 0.75,
                        'min_pnr': 10,
                        'ring_size_factor': 1.4,
                        'center_psf': True,
                        'ssub_B': 2,
                        'init_iter': 2
                    }
                }
            },
            
            'greedy_roi_no_patches_config': {
                'name': 'Greedy ROI No Patches (Optimized for Your Data)',
                'description': 'Greedy ROI with your proven parameters - global background handling',
                'params': {
                    # Data parameters - YOUR PROVEN VALUES
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 1.08,                  # YOUR frame rate
                    'decay_time': 20,            # YOUR decay time
                    'dxy': (1.243, 1.243),      # YOUR spatial resolution
                    
                    # Motion correction parameters
                    'motion_correct': True,
                    'pw_rigid': False,
                    'max_shifts': (5, 5),
                    'strides': (48, 48),
                    'overlaps': (24, 24),
                    'max_deviation_rigid': 3,
                    'border_nan': 'copy',
                    
                    # Parameters for source extraction and deconvolution - YOUR PROVEN VALUES
                    'p': 2,                      # YOUR autoregressive order
                    'gnb': 2,                    # Global background components
                    'merge_thr': 0.2,            # YOUR merge threshold
                    'rf': None,                  # No patches - global processing
                    'stride_cnmf': None,         # No patches
                    'K': 400,                    # Expected number of components (increased for global processing)
                    'gSig': [4, 4],              # Calculated as 0.5*d_px = 0.5*8 = 4 (from cell_diameter=10µm, dxy=1.243µm/px)
                    'method_init': 'greedy_roi', # Use greedy ROI method
                    'ssub': 1,
                    'tsub': 1,
                    'bas_nonneg': True,          # YOUR setting
                    'only_init': False,          # Changed from your True to get full pipeline
                    
                    # Component evaluation - YOUR PROVEN VALUES
                    'min_SNR': 2.0,              # YOUR min SNR
                    'rval_thr': 0.85,            # YOUR space correlation threshold
                    'min_cnn_thr': 0.99,         # YOUR CNN threshold
                    'cnn_lowest': 0.1,           # YOUR CNN lowest threshold
                    
                    # Parameters for component evaluation
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 1.08,               # YOUR frame rate
                        'decay_time': 20,         # YOUR decay time
                        'nb': 2,                  # Global background components
                        'rf': None,               # No patches
                        'K': 400,
                        'gSig': [4, 4],           # Calculated: 0.5*d_px = 0.5*8 = 4
                        'stride': None,           # No patches
                        'method_init': 'greedy_roi',
                        'rolling_sum': True,
                        'merge_thr': 0.2,         # YOUR merge threshold
                        'n_processes': 4,
                        'only_init': False,       # Changed from your True to get full pipeline
                        'ssub': 1,
                        'tsub': 1,
                        'p': 2,                   # YOUR autoregressive order
                        'bas_nonneg': True,       # YOUR setting
                        'min_SNR': 2.0,           # YOUR min SNR
                        'rval_thr': 0.85,         # YOUR rval threshold
                        'use_cnn': True,          # Use CNN for component classification
                        'min_cnn_thr': 0.99,     # YOUR CNN threshold
                        'cnn_lowest': 0.1         # YOUR CNN lowest threshold
                    }
                }
            },
            
            'fast_config': {
                'name': 'Fast Processing',
                'description': 'Optimized for speed with minimal quality loss',
                'params': {
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 30,
                    'decay_time': 0.4,
                    'motion_correct': False,     # Skip motion correction for speed
                    'p': 0,                      # No deconvolution
                    'gnb': 1,                    # Fewer background components
                    'merge_thr': 0.9,            # Higher merge threshold
                    'rf': 60,                    # Larger patches
                    'stride_cnmf': 30,
                    'K': 3,                      # Fewer components per patch
                    'gSig': [5, 5],              # Slightly larger expected size
                    'method_init': 'greedy_roi',
                    'ssub': 2,                   # More spatial subsampling
                    'tsub': 2,                   # More temporal subsampling
                    'only_init': False,           # Only initialization, no refinement
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 30,
                        'nb': 1,
                        'rf': 60,
                        'K': 3,
                        'gSig': [5, 5],
                        'stride': 30,
                        'method_init': 'greedy_roi',
                        'rolling_sum': True,
                        'merge_thr': 0.9,
                        'n_processes': 4,
                        'only_init': False,
                        'ssub': 2,
                        'tsub': 2
                    }
                }
            },
            
            'high_quality_config': {
                'name': 'High Quality Processing',
                'description': 'Best quality results with longer processing time',
                'params': {
                    'fnames': None,  # Set via --movie or movie_file= argument
                    'fr': 30,
                    'decay_time': 0.4,
                    'motion_correct': True,
                    'pw_rigid': True,            # Piecewise rigid motion correction
                    'max_shifts': (6, 6),
                    'strides': (32, 32),         # Smaller patches for better correction
                    'overlaps': (16, 16),
                    'max_deviation_rigid': 3,
                    'border_nan': 'copy',
                    'p': 2,                      # Higher order AR process
                    'gnb': 3,                    # More background components
                    'merge_thr': 0.7,            # Lower merge threshold
                    'rf': 30,                    # Smaller patches
                    'stride_cnmf': 15,
                    'K': 6,                      # More components per patch
                    'gSig': [3, 3],              # Smaller expected size
                    'method_init': 'corr_pnr',
                    'ssub': 1,
                    'tsub': 1,
                    'min_corr': 0.8,
                    'min_pnr': 15,
                    'ring_size_factor': 1.2,
                    'center_psf': True,
                    'ssub_B': 1,
                    'init_iter': 3,
                    'only_init': False,          # Full processing with refinement
                    'opts_dict': {
                        'fnames': None,  # Set via --movie or movie_file= argument
                        'fr': 30,
                        'nb': 3,
                        'rf': 30,
                        'K': 6,
                        'gSig': [3, 3],
                        'stride': 15,
                        'method_init': 'corr_pnr',
                        'rolling_sum': True,
                        'merge_thr': 0.7,
                        'n_processes': 4,
                        'only_init': False,
                        'ssub': 1,
                        'tsub': 1,
                        'min_corr': 0.8,
                        'min_pnr': 15,
                        'ring_size_factor': 1.2,
                        'center_psf': True,
                        'ssub_B': 1,
                        'init_iter': 3
                    }
                }
            }
        }
    
    def list_configs(self):
        """List available configurations"""
        print("\nAvailable CNMF Configurations:")
        print("=" * 50)
        for key, config in self.configs.items():
            print(f"\n{key}:")
            print(f"  Name: {config['name']}")
            print(f"  Description: {config['description']}")
            print(f"  Method: {config['params']['method_init']}")
            print(f"  Patches: {'Yes' if config['params'].get('rf') else 'No'}")
            print(f"  Motion Correction: {'Yes' if config['params'].get('motion_correct', True) else 'No'}")
    
    def get_config(self, config_name):
        """Get a specific configuration"""
        if config_name not in self.configs:
            raise ValueError(f"Configuration '{config_name}' not found. Available: {list(self.configs.keys())}")
        return self.configs[config_name]
    
    def create_custom_config(self, base_config, modifications):
        """Create a custom configuration based on existing one"""
        config = self.configs[base_config].copy()
        config['params'].update(modifications)
        return config
    
    def run_cnmf(self, config_name, movie_file=None, enable_debug=False, save_results=True, max_frames=None):
        """
        Run CNMF with specified configuration
        
        Args:
            config_name: Name of configuration to use
            movie_file: Path to movie file (overrides config default)
            enable_debug: Whether to enable debug tracking
            save_results: Whether to save results
            max_frames: Maximum number of frames to load (None = load all frames)
        """
        print(f"\n{'='*60}")
        print(f"Running CNMF with configuration: {config_name}")
        print(f"{'='*60}")

        # Deferred imports to avoid circular import with cnmf.py
        import caiman as cm
        from instrumented_cnmf import CNMF
        from caiman.source_extraction.cnmf import params as cnmf_params
        
        # Get configuration
        config = self.get_config(config_name)
        params = config['params'].copy()
        
        # Override movie file if provided
        if movie_file:
            params['fnames'] = [movie_file]
            params['opts_dict']['fnames'] = [movie_file]

        if params.get('fnames') is None:
            raise ValueError(
                "No movie file specified. Pass movie_file= or use --movie."
            )
        
        print(f"Configuration: {config['name']}")
        print(f"Description: {config['description']}")
        print(f"Movie file: {params['fnames'][0]}")
        print(f"Method: {params['method_init']}")
        print(f"Debug enabled: {enable_debug}")
        
        # Start timing
        start_time = time.time()
        
        try:
            # Start cluster for parallel processing
            print("\nStarting cluster...")
            c, dview, n_processes = cm.cluster.setup_cluster(
                backend='local', n_processes=None, single_thread=False)
            
            # Setup parameters
            opts = cnmf_params.CNMFParams(params_dict=params['opts_dict'])
            
            print(f"\nParameters summary:")
            print(f"  Frame rate: {opts.data['fr']}")
            print(f"  Decay time: {opts.data['decay_time']}")
            print(f"  Method: {opts.init['method_init']}")
            print(f"  gSig: {opts.init['gSig']}")
            print(f"  K: {opts.init['K']}")
            if opts.init['method_init'] == 'corr_pnr':
                print(f"  Min correlation: {opts.init['min_corr']}")
                print(f"  Min PNR: {opts.init['min_pnr']}")
            print(f"  Merge threshold: {opts.merging['merge_thr']}")
            print(f"  Patches RF: {opts.patch['rf']}")
            if max_frames:
                print(f"  Max frames: {max_frames}")
            
            # Frame limiting (if specified)
            if max_frames:
                print(f"\nLimiting to {max_frames} frames...")
                from tifffile import imread
                
                # Load and limit frames
                Y_full = imread(params['fnames'][0])
                if len(Y_full.shape) == 3:  # T, d1, d2
                    Y_limited = Y_full[:max_frames]
                    print(f"  Original frames: {Y_full.shape[0]}")
                    print(f"  Limited to: {Y_limited.shape[0]} frames")
                    
                    # Save limited movie temporarily
                    import tempfile
                    import tifffile
                    temp_dir = tempfile.mkdtemp()
                    limited_movie_path = os.path.join(temp_dir, 'limited_movie.tif')
                    tifffile.imwrite(limited_movie_path, Y_limited)
                    
                    # Update file paths to use limited movie
                    params['fnames'] = [limited_movie_path]
                    params['opts_dict']['fnames'] = [limited_movie_path]
                    opts.set('data', {'fnames': [limited_movie_path]})  # Update opts too
                    print(f"  Using limited movie: {limited_movie_path}")
            
            # CNMF processing - Let CNMF handle motion correction, memory mapping, and processing
            print(f"\nRunning CNMF with integrated pipeline...")
            cnm = CNMF(n_processes=n_processes, dview=dview, params=opts)
            cnm.fit_file(motion_correct=params.get('motion_correct', True))  # Use fit_file for complete pipeline
            
            # Results summary
            print(f"\nCNMF Results:")
            print(f"  Total components found: {cnm.estimates.A.shape[1] if cnm.estimates.A is not None else 0}")
            if hasattr(cnm, 'dims') and cnm.dims is not None:
                print(f"  Image dimensions: {cnm.dims}")
            if hasattr(cnm, 'estimates') and hasattr(cnm.estimates, 'C') and cnm.estimates.C is not None:
                print(f"  Number of frames: {cnm.estimates.C.shape[1]}")
            
            # Save results if requested
            if save_results:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                results_file = self.results_dir / f"cnmf_results_{config_name}_{timestamp}.hdf5"
                print(f"\nSaving results to: {results_file}")
                cnm.save(str(results_file))
                
                # Save configuration used (with actual movie path)
                config_to_save = config.copy()
                config_to_save['params'] = config_to_save['params'].copy()
                config_to_save['params']['fnames'] = params['fnames']
                config_file = self.results_dir / f"config_{config_name}_{timestamp}.json"
                with open(config_file, 'w') as f:
                    json.dump(config_to_save, f, indent=2)
                
            # Stop cluster
            cm.cluster.stop_server(dview=dview)
            
            end_time = time.time()
            processing_time = end_time - start_time
            print(f"\nProcessing completed in {processing_time:.2f} seconds")
            
            return cnm, results_file if save_results else None
            
        except Exception as e:
            print(f"\nError during processing: {str(e)}")
            print("Full traceback:")
            import traceback
            traceback.print_exc()
            try:
                cm.cluster.stop_server(dview=dview)
            except:
                pass
            raise

    def save_config(self, config_name, config_data, filepath=None):
        """Save a configuration to file"""
        if filepath is None:
            filepath = self.results_dir / f"{config_name}.json"
        
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Configuration saved to: {filepath}")
    
    def load_config(self, filepath):
        """Load a configuration from file"""
        with open(filepath, 'r') as f:
            return json.load(f)


def main():
    """Main function for command line interface"""
    parser = argparse.ArgumentParser(description='CNMF Manager - Run CNMF with different configurations')
    
    parser.add_argument('--config', type=str, default='greedy_roi_config',
                       help='Configuration to use (default: greedy_roi_config)')
    parser.add_argument('--movie', type=str,
                       help='Path to movie file (overrides config default)')
    parser.add_argument('--list-configs', action='store_true',
                       help='List available configurations and exit')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug tracking')
    parser.add_argument('--no-save', action='store_true',
                       help='Do not save results')
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = CNMFManager()
    
    # List configurations if requested
    if args.list_configs:
        manager.list_configs()
        return
    
    # Run single configuration
    try:
        cnm, results_file = manager.run_cnmf(
            config_name=args.config,
            movie_file=args.movie,
            enable_debug=args.debug,
            save_results=not args.no_save
        )
        print(f"\nProcessing completed successfully!")
        if results_file:
            print(f"Results saved to: {results_file}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
