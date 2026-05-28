import subprocess
import sys
import os

def run_pytest(args):
    """Executa o pytest com os argumentos fornecidos."""
    cmd = [sys.executable, "-m", "pytest"] + args
    return subprocess.run(cmd)

def main():
    print("\n" + "="*50)
    print("🕒 BANCO DE HORAS - INTERACTIVE TEST RUNNER")
    print("="*50 + "\n")

    # Primeira execução: Todas as baterias de testes
    print("🚀 Executando suíte completa de testes...")
    # --tb=short para manter a saída limpa
    # -v para ver quais testes estão passando
    result = run_pytest(["tests/", "--tb=short", "-v"])

    while result.returncode != 0:
        print("\n" + "!"*50)
        print("⚠️  AVISO: Ocorreram falhas nos testes acima.")
        print("!"*50)
        
        print("\nInstruções:")
        print("1. Analise o erro acima.")
        print("2. Corrija o código fonte.")
        print("3. Escolha uma opção abaixo para continuar.")
        
        choice = input("\n[ENTER] Repetir APENAS os testes que falharam\n[A] Executar TODOS os testes novamente\n[Q] Sair do executor\n\nEscolha: ").strip().lower()

        if choice == 'q':
            print("\nExcluindo execução. Corrija os erros e tente novamente.")
            sys.exit(result.returncode)
        elif choice == 'a':
            print("\n🔄 Reiniciando suíte completa...")
            result = run_pytest(["tests/", "--tb=short", "-v"])
        else:
            print("\n🛠️  Repetindo apenas falhas anteriores (--lf)...")
            # --lf (last failed) é nativo do pytest e executa apenas o que falhou na última vez
            result = run_pytest(["--lf", "--tb=short", "-v"])
            
            if result.returncode == 0:
                print("\n✅ Correção confirmada para os testes que falharam!")
                print("🔄 Executando suíte completa para garantir que não houve regressões...")
                result = run_pytest(["tests/", "--tb=short", "-v"])

    print("\n" + "="*50)
    print("✨ VERIFICAÇÃO CONCLUÍDA: TODOS OS TESTES PASSARAM!")
    print("✔ [CHECK]")
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário. Saindo...")
        sys.exit(1)
