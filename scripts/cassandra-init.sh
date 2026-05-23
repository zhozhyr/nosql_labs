set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

sed "s/\${CASSANDRA_KEYSPACE}/${CASSANDRA_KEYSPACE}/g" "${SCRIPT_DIR}/cassandra-init.cql" | cqlsh "${CASSANDRA_HOSTS}" "${CASSANDRA_PORT}"
echo "Cassandra schema init done."
