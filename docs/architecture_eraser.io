title Security Analytics Lab Architecture

Docker Services [icon: docker] {
  Zeek Monitor [icon: activity, label: "Zeek Monitor - eth0"]
  SIEM Simulator [icon: server, label: "SIEM Simulator (:8080)"]
  Fluentd [icon: feather, label: "Fluentd"]
  Bytewax ELT [icon: shuffle, label: "Bytewax ELT"]
  Trino [icon: database, label: "Trino (:18080)"]
  Superset [icon: bar-chart-2, label: "Superset (:8088)"]
  Jupyter Spark [icon: book-open, label: "Jupyter + Spark (:8888)"]
  AI Agent UI [icon: cpu, label: "AI Agent UI (:5000)"]
  Splunk DB Connect [icon: database, label: "Splunk via DB Connect"]

  
}

Vast Cluster [icon: server] {
  Vector DB [icon: database, label: "Vector DB"]
  Vast Kafka Broker [icon: message-square, label: "Vast Kafka Broker"]
  Vast Database [icon: database, label: "Vast Database"]
}

// Connections within Docker Services
SIEM Simulator > Fluentd: Simulate Log Files
SIEM Simulator > Zeek Monitor: Simulated Network Traffic
Superset > Trino: Queries
AI Agent UI > Trino: Queries
Splunk DB Connect > Trino: Queries

// Connections within Docker Host UIs (UI nodes are for user access, not data flow)

// Connections between Docker Services and Vast Cluster
Fluentd > Vast Kafka Broker: Publishes
Zeek Monitor > Vast Kafka Broker: Publishes
Bytewax ELT > Vast Database: Writes To
Bytewax ELT > Vector DB: Writes To
Trino > Vast Database: Queries
Jupyter Spark > Vast Database: Queries
AI Agent UI > Vector DB: Queries

// Kafka connections
Bytewax ELT < Vast Kafka Broker: Consumes
SIEM Simulator < Vast Kafka Broker: Consumes
