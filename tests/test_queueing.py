import math
import unittest

from queueing import MM1, MM1K, MMInf, MMNN, MMC, MMCK, analytics
from queueing.distributions import ExponentialSampler
from queueing.generators import poisson_arrivals
from queueing.network import TwoStationNetwork


class QueueingTests(unittest.TestCase):
    def test_seeded_sampler_and_arrivals_repeat(self):
        a=ExponentialSampler(2, seed=5); b=ExponentialSampler(2, seed=5)
        self.assertEqual([a.sample() for _ in range(5)], [b.sample() for _ in range(5)])
        self.assertEqual(poisson_arrivals(4, 20, seed=8), poisson_arrivals(4, 20, seed=8))

    def test_validation_and_analytic_values(self):
        with self.assertRaises(ValueError): MM1(1, 0)
        with self.assertRaises(ValueError): MMCK(2, 1, 3, 2)
        self.assertAlmostEqual(analytics.mm1(2, 4)["L"], 1.0)
        self.assertAlmostEqual(sum(analytics.mm1k(2, 2, 4)["state_probabilities"]), 1)
        mm1k=analytics.mm1k(2, 1, 2)
        self.assertAlmostEqual(mm1k["Lq"], 4/7)
        self.assertAlmostEqual(analytics.erlang_b(1, 2, 1), 1/3)
        self.assertLess(analytics.mmc(2, 3, 2)["P0"], 1)
        self.assertAlmostEqual(sum(analytics.mmck(2, 3, 2, 4)["state_probabilities"]), 1)

    def test_unbounded_queue_and_lifecycle(self):
        model=MM1(1, 5, seed=3)
        # Replace generated stream with deterministic simultaneous arrivals.
        model._events.clear()
        from queueing.events import QueueEvent, EXTERNAL_ARRIVAL
        model._push(QueueEvent(0, EXTERNAL_ARRIVAL, 10))
        model._push(QueueEvent(0, EXTERNAL_ARRIVAL, 11))
        model._push(QueueEvent(0, EXTERNAL_ARRIVAL, 12))
        model._schedule_arrival=lambda at: None
        result=model.run(10)
        self.assertEqual(model.accepted_arrivals, 3)
        self.assertEqual(model.blocked_arrivals, 0)
        self.assertEqual(model.queue_length, 0)
        self.assertEqual(model.departures, 3)
        self.assertEqual([row["customer_id"] for row in result["customer_observations"]], [10, 11, 12])
        self.assertTrue(all(row["waiting_time"] >= 0 for row in result["customer_observations"]))

    def test_capacities_servers_and_blocking(self):
        for model in (MM1K(10, 1, 2, seed=2), MMNN(10, 1, 2, seed=2),
                      MMCK(10, 1, 2, 3, seed=2)):
            model.run(10)
            self.assertGreater(model.blocked_arrivals, 0)
            self.assertLessEqual(model.system_population, model.capacity)
        self.assertIsNone(MMInf(1, 1, seed=2).servers)
        self.assertEqual(MMNN(1, 1, 3).capacity, 3)
        self.assertEqual(MMC(1, 2, 4).servers, 4)

    def test_time_weighted_state_and_horizon(self):
        model=MM1(1, 1, seed=1)
        model._events.clear()
        from queueing.events import QueueEvent, EXTERNAL_ARRIVAL
        model._push(QueueEvent(2, EXTERNAL_ARRIVAL, 0))
        model._schedule_arrival=lambda at: None
        result=model.run(1)
        self.assertEqual(result["events_processed"],0)
        self.assertEqual(model.now,1)
        self.assertEqual(model.system_population,0)
        result=model.run(3)
        self.assertEqual(model.attempted_arrivals,1)
        self.assertGreater(result["average_system_population"],0)

    def test_max_events_does_not_advance_past_pending_events(self):
        model=MM1(1, 2, seed=4)
        result=model.run(100, max_events=1)
        self.assertEqual(result["events_processed"], 1)
        self.assertLess(model.now, 100)
        self.assertGreaterEqual(model._peek().timestamp, model.now)
        model.run(model.now + 1)

    def test_network_preserves_ids(self):
        network=TwoStationNetwork(2, 5, 5, seed=9)
        result=network.run(20)
        self.assertGreater(result["station_1"]["departures"],0)
        first_departures={row["customer_id"]: row["departure_time"]
                          for row in result["station_1_observations"]}
        second_rows=result["station_2_observations"]
        ids={row["customer_id"] for row in second_rows}
        self.assertTrue(ids.issubset(set(result["routed_customer_ids"])))
        for row in second_rows:
            self.assertAlmostEqual(row["arrival_time"], first_departures[row["customer_id"]])

    def test_dev1_dispatcher_integration(self):
        from spe_core.dispatcher import SpeSequentialDispatcher
        model=MM1(1, 3, seed=12)
        dispatcher=SpeSequentialDispatcher(end_time=40)
        model.register_with_dispatcher(dispatcher, lp_id=7)
        stats=dispatcher.run()
        result=model.finish(40)
        self.assertGreater(stats["events_processed"], 0)
        self.assertGreater(result["attempted_arrivals"], 0)
        self.assertLessEqual(result["accepted_arrivals"], result["attempted_arrivals"])

    def test_statistical_mm1(self):
        result=MM1(1, 3, seed=77).run(12000)
        theory=analytics.mm1(1,3)
        self.assertTrue(math.isclose(result["average_system_population"],theory["L"],abs_tol=.12))

    def test_statistical_model_references(self):
        cases=(
            (MM1K(2,3,4,seed=21), analytics.mm1k(2,3,4)["L"], .10),
            (MMInf(2,3,seed=22), analytics.mminf(2,3)["L"], .06),
            (MMNN(3,2,3,seed=23), analytics.mnn(3,2,3)["L"], .08),
            (MMC(2,3,2,seed=24), analytics.mmc(2,3,2)["L"], .07),
            (MMCK(4,3,2,5,seed=25), analytics.mmck(4,3,2,5)["L"], .08),
        )
        for model, expected, tolerance in cases:
            with self.subTest(model=type(model).__name__):
                result=model.run(12000)
                self.assertAlmostEqual(result["average_system_population"], expected,
                                       delta=tolerance)


if __name__ == "__main__": unittest.main()
