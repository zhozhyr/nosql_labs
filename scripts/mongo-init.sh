set -e

echo "Waiting for config server..."
until mongosh --host ${CONFIGSVR_HOST} --port ${CONFIGSVR_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done

echo "Init config replica set..."
mongosh --host ${CONFIGSVR_HOST} --port ${CONFIGSVR_PORT} --eval '
  try {
    rs.status()
  } catch (e) {
    rs.initiate({
      _id: "'"${CONFIG_REPLSET}"'",
      configsvr: true,
      members: [
        { _id: 0, host: "'"${CONFIGSVR_HOST}:${CONFIGSVR_PORT}"'" }
      ]
    })
  }
'

echo "Waiting for shard nodes..."
until mongosh --host ${SHARD1_PRIMARY_HOST} --port ${SHARD1_PRIMARY_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done
until mongosh --host ${SHARD1_SECONDARY_1_HOST} --port ${SHARD1_SECONDARY_1_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done
until mongosh --host ${SHARD1_SECONDARY_2_HOST} --port ${SHARD1_SECONDARY_2_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done
until mongosh --host ${SHARD2_PRIMARY_HOST} --port ${SHARD2_PRIMARY_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done
until mongosh --host ${SHARD2_SECONDARY_1_HOST} --port ${SHARD2_SECONDARY_1_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done
until mongosh --host ${SHARD2_SECONDARY_2_HOST} --port ${SHARD2_SECONDARY_2_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done

echo "Init shard 1 replica set..."
mongosh --host ${SHARD1_PRIMARY_HOST} --port ${SHARD1_PRIMARY_PORT} --eval '
  try {
    rs.status()
  } catch (e) {
    rs.initiate({
      _id: "'"${SHARD1_REPLSET}"'",
      members: [
        { _id: 0, host: "'"${SHARD1_PRIMARY_HOST}:${SHARD1_PRIMARY_PORT}"'" },
        { _id: 1, host: "'"${SHARD1_SECONDARY_1_HOST}:${SHARD1_SECONDARY_1_PORT}"'" },
        { _id: 2, host: "'"${SHARD1_SECONDARY_2_HOST}:${SHARD1_SECONDARY_2_PORT}"'" }
      ]
    })
  }
'

echo "Init shard 2 replica set..."
mongosh --host ${SHARD2_PRIMARY_HOST} --port ${SHARD2_PRIMARY_PORT} --eval '
  try {
    rs.status()
  } catch (e) {
    rs.initiate({
      _id: "'"${SHARD2_REPLSET}"'",
      members: [
        { _id: 0, host: "'"${SHARD2_PRIMARY_HOST}:${SHARD2_PRIMARY_PORT}"'" },
        { _id: 1, host: "'"${SHARD2_SECONDARY_1_HOST}:${SHARD2_SECONDARY_1_PORT}"'" },
        { _id: 2, host: "'"${SHARD2_SECONDARY_2_HOST}:${SHARD2_SECONDARY_2_PORT}"'" }
      ]
    })
  }
'

echo "Waiting for replica sets to elect primary..."
sleep 15

echo "Waiting for mongos..."
until mongosh --host ${MONGODB_HOST} --port ${MONGODB_PORT} --eval "db.adminCommand('ping')" >/dev/null 2>&1; do sleep 2; done

echo "Adding shards to mongos..."
mongosh --host ${MONGODB_HOST} --port ${MONGODB_PORT} --eval '
  try {
    sh.addShard("'"${SHARD1_REPLSET}/${SHARD1_PRIMARY_HOST}:${SHARD1_PRIMARY_PORT},${SHARD1_SECONDARY_1_HOST}:${SHARD1_SECONDARY_1_PORT},${SHARD1_SECONDARY_2_HOST}:${SHARD1_SECONDARY_2_PORT}"'")
  } catch (e) {
    print("Shard 1: " + e.message)
  }

  try {
    sh.addShard("'"${SHARD2_REPLSET}/${SHARD2_PRIMARY_HOST}:${SHARD2_PRIMARY_PORT},${SHARD2_SECONDARY_1_HOST}:${SHARD2_SECONDARY_1_PORT},${SHARD2_SECONDARY_2_HOST}:${SHARD2_SECONDARY_2_PORT}"'")
  } catch (e) {
    print("Shard 2: " + e.message)
  }

  try {
    sh.enableSharding("'"${MONGODB_DATABASE}"'")
  } catch (e) {
    print("Enable sharding: " + e.message)
  }

  try {
    db = db.getSiblingDB("'"${MONGODB_DATABASE}"'")
    sh.shardCollection("'"${MONGODB_DATABASE}.events"'", { created_by: "hashed" })
  } catch (e) {
    print("Shard collection: " + e.message)
  }

  quit(0)
'
