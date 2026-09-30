#!/usr/bin/env bash
# 在无 root 环境下，把 PostgreSQL 15 + PostGIS 3 解压到用户目录并启动。
# 如果系统已有 PostgreSQL（含 postgis），可跳过本脚本，直接 export PLUME_DSN=...
set -euo pipefail

PREFIX="${PLUME_LOCAL:-/tmp/pglocal}"
PGDATA="${PLUME_PGDATA:-/tmp/pgdata}"
PORT="${PLUME_PORT:-55432}"
DEBS=/tmp/pgdebs
MIRROR="${DEBIAN_MIRROR:-http://ftp.debian.org/debian/pool/main}"

mkdir -p "$DEBS" "$PREFIX"

dl() { # dl <local-name> <url>
  [ -s "$DEBS/$1" ] || curl -sSL --max-time 500 -o "$DEBS/$1" "$2"
  dpkg-deb -x "$DEBS/$1" "$PREFIX"
}

if [ ! -x "$PREFIX/usr/lib/postgresql/15/bin/postgres" ]; then
  echo "[setup_db] 下载 PostgreSQL 15（arm64/amd64 同源结构；其他架构请自行替换包名）"
  SERVER=$(curl -sSL "$MIRROR/p/postgresql-15/" \
    | grep -oE 'postgresql-15_[^"]+_arm64\.deb' | sort -u | tail -1 || true)
  CLIENT=$(curl -sSL "$MIRROR/p/postgresql-15/" \
    | grep -oE 'postgresql-client-15_[^"]+_arm64\.deb' | sort -u | tail -1 || true)
  dl pg-server.deb "$MIRROR/p/postgresql-15/$SERVER"
  dl pg-client.deb "$MIRROR/p/postgresql-15/$CLIENT"
  dl geos.deb      "$MIRROR/g/geos/libgeos3.11.1_3.11.1-1_arm64.deb"
  dl geosc.deb     "$MIRROR/g/geos/libgeos-c1v5_3.11.1-1_arm64.deb"
  dl proj.deb      "$MIRROR/p/proj/libproj25_9.1.1-1+b1_arm64.deb"
  dl jsonc.deb     "$MIRROR/j/json-c/libjson-c5_0.16-2_arm64.deb"
  dl protoc.deb    "$MIRROR/p/protobuf-c/libprotobuf-c1_1.4.1-1+b1_arm64.deb"
  dl postgis.deb   "$MIRROR/p/postgis/postgresql-15-postgis-3_3.3.2+dfsg-1+b1_arm64.deb"
  dl postgis-sql.deb "$MIRROR/p/postgis/postgresql-15-postgis-3-scripts_3.3.2+dfsg-1_all.deb"
fi

# Debian 打包把控制文件命名为 postgis-3.control，而 CREATE EXTENSION 需要 postgis.control
EXT="$PREFIX/usr/share/postgresql/15/extension"
[ -f "$EXT/postgis.control" ] || cp "$EXT/postgis-3.control" "$EXT/postgis.control"

export PATH="$PREFIX/usr/lib/postgresql/15/bin:$PATH"
export LD_LIBRARY_PATH="$(find "$PREFIX/usr/lib" -type d | tr '\n' ':')${LD_LIBRARY_PATH:-}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "[setup_db] initdb → $PGDATA"
  initdb -D "$PGDATA" -U plume --auth=trust --encoding=UTF8 --locale=C
  cat >> "$PGDATA/postgresql.conf" <<EOF

# plume-lab rootless instance
port = $PORT
unix_socket_directories = '/tmp'
listen_addresses = ''
dynamic_library_path = '\$libdir:$PREFIX/usr/lib/postgresql/15/lib'
EOF
fi

pg_ctl -D "$PGDATA" -l /tmp/pglog -w start || true
sleep 1

for db in plume_lab plume_lab_test; do
  psql -h /tmp -p "$PORT" -U plume -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
    || createdb -h /tmp -p "$PORT" -U plume "$db"
  psql -h /tmp -p "$PORT" -U plume -d "$db" -tAc \
    "SELECT 1 FROM pg_extension WHERE extname='postgis'" | grep -q 1 \
    || psql -h /tmp -p "$PORT" -U plume -d "$db" -c "CREATE EXTENSION postgis;"
done

echo "[setup_db] 就绪：localhost socket /tmp 端口 $PORT，库 plume_lab / plume_lab_test"
psql -h /tmp -p "$PORT" -U plume -d plume_lab -tc "SELECT postgis_full_version();"
