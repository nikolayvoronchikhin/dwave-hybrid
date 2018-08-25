#!/usr/bin/env python
"""
Kerberos prototype: runs N samplers in parallel. Behaves like a dimod sampler.
"""

import dimod
from hades.samplers import (
    QPUSubproblemAutoEmbeddingSampler,
    SimulatedAnnealingSubproblemSampler,
    InterruptableTabuSampler)
from hades.decomposers import (
    RandomSubproblemDecomposer, IdentityDecomposer, EnergyImpactDecomposer)
from hades.composers import SplatComposer
from hades.core import State, SampleSet
from hades.flow import RacingBranches, ArgMinFold, SimpleIterator
from hades.utils import random_sample


class KerberosSampler(dimod.Sampler):
    """An opinionated dimod-compatible hybrid asynchronous decomposition sampler
    for problems of arbitrary structure and size.

    Examples:
        This example solves a two-variable Ising model.

        >>> import dimod
        >>> response = KerberosSampler().sample_ising(
        ...                     {'a': -0.5, 'b': 1.0}, {('a', 'b'): -1})
        >>> response.data_vectors['energy']
        array([-1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5])

    """

    properties = None
    parameters = None

    def __init__(self):
        self.parameters = {'max_iter': [],
                           'convergence': [],
                           'num_reads': [],
                           'sa_sweeps': [],
                           'qpu_reads': [],
                           'max_subproblem_size': []}
        self.properties = {}

    def sample(self, bqm, init_solution=None, max_iter=100, convergence=10, num_reads=1,
            sa_sweeps=1000, qpu_reads=100, max_subproblem_size=50):
        """Run Tabu search, Simulated annealing and QPU subproblem sampling (for
        high energy impact problem variables) in parallel and return the best
        samples.
        """
        subproblem_size = min(len(bqm), max_subproblem_size)

        iteration = RacingBranches(
            InterruptableTabuSampler(bqm),
            IdentityDecomposer(bqm)
                | SimulatedAnnealingSubproblemSampler(num_reads=1, sweeps=sa_sweeps)
                | SplatComposer(bqm),
            RandomSubproblemDecomposer(bqm, size=subproblem_size)
                | QPUSubproblemAutoEmbeddingSampler(num_reads=qpu_reads)
                | SplatComposer(bqm),
            EnergyImpactDecomposer(bqm, max_size=subproblem_size, min_diff=subproblem_size//2)
                | QPUSubproblemAutoEmbeddingSampler(num_reads=qpu_reads)
                | SplatComposer(bqm),
        ) | ArgMinFold()
        main = SimpleIterator(iteration, max_iter=max_iter, convergence=convergence)

        init_state = State.from_sample(random_sample(bqm), bqm)
        final_state = main.run(init_state)

        return dimod.Response.from_future(final_state, result_hook=lambda f: f.result().samples)


if __name__ == '__main__':
    response = KerberosSampler().sample_ising({'a': -0.5, 'b': 1.0}, {('a', 'b'): -1})
    print(list(response.data()))