# Aplicativos NJA System

O NJA System possui versões instaláveis para Windows 64 bits e Android. As duas versões abrem o ambiente oficial em `https://njasystem.com.br/` e mantêm os mesmos dados, usuários e permissões do sistema web.

## Downloads públicos

- Windows: `https://github.com/njamarketing/nja-system/releases/latest/download/NJA-System-Windows.exe`
- Android: `https://github.com/njamarketing/nja-system/releases/latest/download/NJA-System-Android.apk`

Os links são permanentes: cada nova release substitui o arquivo entregue por `latest`, sem exigir mudanças na tela de login.

## Geração automática

O workflow `.github/workflows/native-apps.yml` compila os dois aplicativos. Em commits normais, os arquivos ficam como artefatos da execução. Ao publicar uma tag `v*`, os arquivos também são anexados à release do GitHub com os nomes esperados pelos botões do sistema.

O executável Windows é independente do .NET instalado na máquina e usa o WebView2 presente nas versões atuais do Windows. O APK é instalável diretamente. Para distribuir futuramente pela Play Store, deve-se criar uma chave permanente de assinatura, guardá-la nos secrets do GitHub e gerar também um Android App Bundle (`.aab`).

## Compilação local

Windows, com o SDK .NET 8:

```powershell
dotnet publish packaging/windows/NjaSystem.Windows.csproj -c Release -r win-x64 --self-contained true -o dist/windows
```

Android, com Java 17 e Gradle 8.13:

```powershell
Set-Location packaging/android
gradle --no-daemon :app:assembleDebug
```
