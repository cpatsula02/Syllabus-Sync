{pkgs}: {
  deps = [
    pkgs.unzip
    pkgs.wget
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.postgresql
    pkgs.openssl
  ];
}
