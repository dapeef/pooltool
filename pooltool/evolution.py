#! /usr/bin/env python

import pooltool.terminal as terminal

from pooltool.events import *
from pooltool.system import System, SystemHistory, ShotRender
from pooltool.objects import NonObject, DummyBall

import numpy as np

from abc import ABC


class EvolveShot(ABC, System, SystemHistory, ShotRender):
    def __new__(cls, cue=None, table=None, balls=None, progress=terminal.Progress(), run=terminal.Run(), algorithm='event-based'):
        if algorithm not in avail_algorithms:
            raise ValueError(f"You are expecting to evolve the system with algorithm '{algorithm}', which is not one of the "
                             f"possible db_types. Choose from: {list(avail_algorithms.keys())}")

        return super().__new__(avail_algorithms[algorithm])


    def __init__(self, cue=None, table=None, balls=None, run=terminal.Run(), progress=terminal.Progress()):
        self.run = run
        self.progress = progress

        System.__init__(self, cue=cue, table=table, balls=balls)
        SystemHistory.__init__(self)
        ShotRender.__init__(self)


    def simulate(self, t_final=None, strike=True, name="NA"):
        """Run a simulation

        Parameters
        ==========
        t_final : float, None
            The simulation will run until the time is greater than this value. If None, simulation
            is ran until the next event occurs at np.inf

        strike : bool, True
            If True, the cue stick will strike a ball at the start of the simulation. If you already
            struck the cue ball, you should set this to False.

        name : str, 'NA'
            A name for the simulated shot
        """

        self.reset_history()
        self.init_history()

        if strike:
            event = self.cue.strike(t = self.t)
            self.update_history(event)

        energy_start = self.get_system_energy()

        def progress_update():
            """Convenience function for updating progress"""
            energy = self.get_system_energy()
            num_stationary = len([_ for _ in self.balls.values() if _.s == 0])
            msg = f"ENERGY {np.round(energy, 2)}J | STATIONARY {num_stationary} | EVENTS {self.num_events}"
            self.progress.update(msg)
            self.progress.increment(increment_to=int(energy_start - energy))

        self.progress_update = progress_update

        self.run.warning('', header=name, lc='green')
        self.run.info('starting energy', f"{np.round(energy_start, 2)}J")

        self.progress.new("Running", progress_total_items=int(energy_start))
        self.evolution_algorithm(t_final=t_final)
        self.progress.end()

        self.run.info('Finished after', self.progress.t.time_elapsed_precise())
        self.run.info('Number of events', len(self.events), nl_after=1)

        self.continuize()
        self.vectorize_trajectories()
        self.balls['cue'].set_playback_sequence()


    @abstractmethod
    def evolution_algorithm(self):
        pass


class EvolveShotEventBased(EvolveShot):
    def __init__(self, *args, **kwargs):
        EvolveShot.__init__(self, *args, **kwargs)


    def evolution_algorithm(self, t_final=None):
        """The event-based evolution algorithm"""

        while True:
            event = self.get_next_event()

            if event.time == np.inf:
                self.end_history()
                break

            self.evolve(event.time - self.t)
            event.resolve()

            self.update_history(event)

            if (self.num_events % 10) == 0:
                self.progress_update()

            if t_final is not None and self.t >= t_final:
                break


    def evolve(self, dt):
        """Evolves current ball an amount of time dt

        FIXME This is very inefficent. each ball should store its natural trajectory thereby avoid a
        call to the clunky evolve_ball_motion. It could even be a partial function so parameters don't
        continuously need to be passed
        """

        for ball_id, ball in self.balls.items():
            rvw, s = physics.evolve_ball_motion(
                state=ball.s,
                rvw=ball.rvw,
                R=ball.R,
                m=ball.m,
                u_s=ball.u_s,
                u_sp=ball.u_sp,
                u_r=ball.u_r,
                g=ball.g,
                t=dt,
            )
            ball.set(rvw, s, t=(self.t + dt))


    def get_next_event(self):
        # Start by assuming next event doesn't happen
        event = NonEvent(t = np.inf)

        transition_event = self.get_min_transition_event_time()
        if transition_event.time < event.time:
            event = transition_event

        ball_ball_event = self.get_min_ball_ball_event_time()
        if ball_ball_event.time < event.time:
            event = ball_ball_event

        ball_cushion_event = self.get_min_ball_rail_event_time()
        if ball_cushion_event.time < event.time:
            event = ball_cushion_event

        return event


    def get_min_transition_event_time(self):
        """Returns minimum time until next ball transition event"""

        event = NonEvent(t = np.inf)

        for ball in self.balls.values():
            if ball.next_transition_event.time <= event.time:
                event = ball.next_transition_event

        return event


    def get_min_ball_ball_event_time(self):
        """Returns minimum time until next ball-ball collision"""

        dtau_E_min = np.inf
        involved_balls = tuple([DummyBall(), DummyBall()])

        for i, ball1 in enumerate(self.balls.values()):
            for j, ball2 in enumerate(self.balls.values()):
                if i >= j:
                    continue

                if ball1.s == pooltool.stationary and ball2.s == pooltool.stationary:
                    continue

                dtau_E = physics.get_ball_ball_collision_time(
                    rvw1=ball1.rvw,
                    rvw2=ball2.rvw,
                    s1=ball1.s,
                    s2=ball2.s,
                    mu1=(ball1.u_s if ball1.s == pooltool.sliding else ball1.u_r),
                    mu2=(ball2.u_s if ball2.s == pooltool.sliding else ball2.u_r),
                    m1=ball1.m,
                    m2=ball2.m,
                    g1=ball1.g,
                    g2=ball2.g,
                    R=ball1.R
                )

                if dtau_E < dtau_E_min:
                    involved_balls = (ball1, ball2)
                    dtau_E_min = dtau_E

        dtau_E = dtau_E_min

        return BallBallCollision(*involved_balls, t=(self.t + dtau_E))


    def get_min_ball_rail_event_time(self):
        """Returns minimum time until next ball-rail collision"""

        dtau_E_min = np.inf
        involved_agents = tuple([DummyBall(), NonObject()])

        for ball in self.balls.values():
            if ball.s == pooltool.stationary:
                continue

            for rail in self.table.rails.values():
                dtau_E = physics.get_ball_rail_collision_time(
                    rvw=ball.rvw,
                    s=ball.s,
                    lx=rail.lx,
                    ly=rail.ly,
                    l0=rail.l0,
                    mu=(ball.u_s if ball.s == pooltool.sliding else ball.u_r),
                    m=ball.m,
                    g=ball.g,
                    R=ball.R
                )

                if dtau_E < dtau_E_min:
                    involved_agents = (ball, rail)
                    dtau_E_min = dtau_E

        dtau_E = dtau_E_min

        return BallCushionCollision(*involved_agents, t=(self.t + dtau_E))


avail_algorithms = {
    'event-based': EvolveShotEventBased,
}
