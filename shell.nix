{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    go # Go-компилятор
    (python3.withPackages (ps: with ps; [
      fastapi
      uvicorn
      requests
      python-multipart # Критически важно для формы логина (Form(...))
    ]))
  ];

  # Этот текст выведется, когда ты зайдешь в nix-shell
  shellHook = ''
    echo "✅ Окружение MY CINEMA готово!"
    echo "Запускай сервер командой: python Cinema.py"
  '';
}
