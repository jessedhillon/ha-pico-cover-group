{
  description = "pico lutron cover group";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    fp.url = "github:hercules-ci/flake-parts";
    devshell = {
      url = "github:numtide/devshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs:
    inputs.fp.lib.mkFlake { inherit inputs; } {
      systems = inputs.nixpkgs.lib.systems.flakeExposed;
      perSystem =
        { system, pkgs, lib, ... }:
        {
          _module.args.pkgs = import inputs.nixpkgs {
            inherit system;
            config.allowUnfree = true;
            overlays = [
              inputs.devshell.overlays.default
            ];
          };
          devShells.default = pkgs.devshell.mkShell {
            name = "pico lutron cover group";
            motd = "{32}activated{reset}\n$(type -p menu &>/dev/null && menu)\n";

            env = [
              {
                name = "LD_LIBRARY_PATH" ;
                value = pkgs.lib.makeLibraryPath [
                  pkgs.file
                  pkgs.stdenv.cc.cc.lib
                ];
              }
            ];

            packages = with pkgs; [
              (python312.withPackages (
                pypkgs: with pypkgs; [
                  pip
                  yarl
                ]
              ))
              file
              gh
              poetry
              pyright
              ruff
            ];

            commands = [
              {
                name = "format";
                command = ''
                pushd $PRJ_ROOT;
                (ruff format -q custom_components/ && isort -q --dt custom_components/);
                popd'';
                help = "apply ruff, isort, prettier formatting";
              }

              {
                name = "check";
                command = ''
                pushd $PRJ_ROOT;
                echo "propel"
                (ruff check propel/ || true);
                pyright propel/;
                echo "migrations"
                (ruff check migrations/ || true);
                pyright migrations/;
                echo "tests"
                (ruff check tests/ || true);
                pyright tests/;
                for dir in propel/web/**/frontend; do
                  pushd $dir
                  npm run lint
                  popd
                done
                popd'';
                help = "run ruff linter, pyright type checker, and eslint";
              }

              {
                name = "up";
                command = "process-compose up";
                help = "bring up services stack";
              }

              {
                name = "make-key";
                command = ''
                python - "$@" << EOF
                import propel.model.id as id
                import sys

                if len(sys.argv) < 2:
                    print("Usage: make-key <KeyName> (e.g. EventID)")
                    sys.exit(1)
                tp = getattr(id, sys.argv[1])
                print(tp())
                EOF'';
                help = "print a random key of the named member of propel.model.id";
              }
            ];
          };
        };
    };
}

