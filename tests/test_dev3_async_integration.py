import unittest
from unittest.mock import patch

from experiments.simulation import simulate


class AsyncQueueIntegration(unittest.TestCase):
    def test_new_requests_enter_while_requester_awaits_completion(self):
        case = {"model": "mm1", "arrival_rate": 1, "service_rate": 1}
        with patch("experiments.simulation.poisson_arrivals", return_value=[1, 1.5, 2]), patch(
            "queueing.base.ExponentialSampler.sample", return_value=1
        ):
            result, _, trace = simulate(case, 1, 3, "asyncio", trace=True)
            control, _, _ = simulate(case, 1, 3, "sequential")
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["unfinished"], 1)
        self.assertEqual(result["waiting_time"], 0.25)
        self.assertEqual(result["response_time"], 1.25)
        self.assertEqual(result["average_queue_length"], 0.5)
        self.assertEqual(result["events_processed"], control["events_processed"])
        self.assertEqual([(e["time"], e["customer_id"]) for e in trace if e["action"] == "resume"],
                         [(2, 0), (3, 1)])
        second = next(e for e in trace if e["action"] == "EXTERNAL_ARRIVAL" and e["customer_id"] == 1)
        self.assertTrue(second["requester_waiting"])
        self.assertEqual(second["outstanding"], 2)

    def test_tandem_notifies_only_after_station_two(self):
        case = {"model": "tandem", "arrival_rate": 1, "service_rate": 1, "service_rate_2": 1}
        with patch("experiments.simulation.poisson_arrivals", return_value=[1, 1.5]), patch(
            "queueing.base.ExponentialSampler.sample", return_value=1
        ):
            result, _, trace = simulate(case, 1, 3, "asyncio", trace=True)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["unfinished"], 1)
        self.assertEqual(result["response_time"], 2)
        self.assertEqual([(e["time"], e["station"]) for e in trace if e["action"] == "resume"], [(3, 2)])
