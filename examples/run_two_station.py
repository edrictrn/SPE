from queueing.network import TwoStationNetwork


if __name__ == "__main__":
    network=TwoStationNetwork(2,3,4,routing_probability=.7,seed=42)
    result=network.run(10000)
    fields=("time", "attempted_arrivals", "accepted_arrivals", "blocked_arrivals",
            "departures", "average_system_population", "average_queue_length",
            "average_busy_servers", "server_utilization")
    print("TwoStationNetwork station 1:",
          {key: result["station_1_metrics"][key] for key in fields})
    print("TwoStationNetwork station 2:",
          {key: result["station_2_metrics"][key] for key in fields})
    print("routed customers:", len(result["routed_customer_ids"]))
