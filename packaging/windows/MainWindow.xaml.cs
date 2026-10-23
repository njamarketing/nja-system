using System.Diagnostics;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace NjaSystem.Windows;

public partial class MainWindow : Window
{
    private static readonly Uri AppUri = new("https://njasystem.com.br/");

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await Browser.EnsureCoreWebView2Async();
            var web = Browser.CoreWebView2;
            web.Settings.IsStatusBarEnabled = false;
            web.Settings.AreDefaultContextMenusEnabled = true;
            web.Settings.IsZoomControlEnabled = true;
            web.Settings.UserAgent += " NJAWindows/1.18.8";
            web.PermissionRequested += OnPermissionRequested;
            web.NewWindowRequested += OnNewWindowRequested;
            web.NavigationCompleted += (_, _) => LoadingPanel.Visibility = Visibility.Collapsed;
            web.Navigate(AppUri.AbsoluteUri);
        }
        catch (Exception ex)
        {
            LoadingPanel.Visibility = Visibility.Visible;
            MessageBox.Show(
                $"Não foi possível abrir o NJA System. Verifique a conexão com a internet e tente novamente.\n\n{ex.Message}",
                "NJA System",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
    }

    private static bool IsTrustedAddress(string? address)
    {
        return Uri.TryCreate(address, UriKind.Absolute, out var uri)
            && uri.Scheme == Uri.UriSchemeHttps
            && (uri.Host.Equals("njasystem.com.br", StringComparison.OrdinalIgnoreCase)
                || uri.Host.EndsWith(".njasystem.com.br", StringComparison.OrdinalIgnoreCase));
    }

    private static void OnPermissionRequested(object? sender, CoreWebView2PermissionRequestedEventArgs e)
    {
        var allowedKind = e.PermissionKind is CoreWebView2PermissionKind.Camera
            or CoreWebView2PermissionKind.Microphone
            or CoreWebView2PermissionKind.Notifications;
        e.State = allowedKind && IsTrustedAddress(e.Uri)
            ? CoreWebView2PermissionState.Allow
            : CoreWebView2PermissionState.Deny;
        e.SavesInProfile = true;
    }

    private void OnNewWindowRequested(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        e.Handled = true;
        if (IsTrustedAddress(e.Uri))
        {
            Browser.CoreWebView2.Navigate(e.Uri);
            return;
        }

        if (Uri.TryCreate(e.Uri, UriKind.Absolute, out var uri)
            && uri.Scheme is "https" or "http")
        {
            Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
        }
    }
}
