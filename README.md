# ARTS-obs

Observing scripts for the ARTS cluster.

## Cluster layout

There is one master node: arts041. All observation scripts, logs and plots are saved to this node, via NFS. For each compound beam (CB), there is a node. CB00 is recorded by arts001, CB01 by arts002, etc.

## Dependencies

- numpy
- matplotlib
- h5py
- pyaml
- astropy

- [PSRDADA](http://psrdada.sourceforge.net/current)
- [AMBER](https://github.com/AA-ALERT/AMBER_setup)
- [fill_ringbuffer](https://github.com/AA-ALERT/ringbuffer-sc4)
- [dadafilterbank](https://github.com/AA-ALERT/dadafilterbank)
- [dadafits](https://github.com/AA-ALERT/dadafits)

