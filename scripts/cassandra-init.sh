set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

envsubst < "${SCRIPT_DIR}/cassandra-init.cql" | cqlsh "${CASSANDRA_HOSTS}" "${CASSANDRA_PORT}"
echo "Cassandra schema init done."
