{ pkgs ? import <nixpkgs> {} }:

with pkgs;

mkShell {
  NIX_LD_LIBRARY_PATH = lib.makeLibraryPath [
    stdenv.cc.cc
  ];
  NIX_LD = lib.fileContents "${stdenv.cc}/nix-support/dynamic-linker";
  buildInputs = [
    python313 poetry python313Packages.build# python tools
    postgresql
    go-task # alternative to make
    nodejs_24
    git
  ];

shellHook = ''
# fix access to dependencies in Python
export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH

# Create DB if does not exist
export LOCALE_ARCHIVE="${pkgs.glibcLocales}/lib/locale/locale-archive"
export PGDATA=$PWD/db/postgres_data
export PGHOST=$PWD/db/postgres
export LOG_PATH=$PWD/db/postgres/LOG
export DATABASE_URL="postgresql:///postgres?host=$PGHOST"
export LC_ALL="en_GB.UTF-8"
export LC_MESSAGES="en_GB.UTF-8"
echo $HOSTNAME

# create directory if need be
if [ ! -d $PGHOST ]; then
mkdir -p $PGHOST
fi
if [ ! -d $PGDATA ]; then
echo 'Initializing postgresql database...'
initdb $PGDATA --auth=trust >/dev/null
fi

pg_ctl restart -l $LOG_PATH -o "-c unix_socket_directories=$PGHOST"
createuser postgres --superuser --createdb

# create user and database if need be
psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'prestagri'" | grep -q 1 || psql -U postgres -c "CREATE DATABASE prestagri"
'';
}
