using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows;
using Microsoft.Web.WebView2.Wpf;
using Microsoft.Win32;

namespace AWGPanel.Desktop;

public partial class MainWindow : Window
{
    private readonly WebView2 Browser = new();
    private readonly string ProfilesDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "NOVA VPN", "profiles");

    public MainWindow()
    {
        InitializeComponent();
        Directory.CreateDirectory(ProfilesDir);
        BrowserHost.Children.Add(Browser);
        Loaded += async (_, _) =>
        {
            await Browser.EnsureCoreWebView2Async();
            Browser.CoreWebView2.NavigationCompleted += (_, _) => UpdateButtons();
            Navigate();
        };
    }

    private void Navigate()
    {
        var text = AddressBox.Text.Trim();
        if (!text.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
            !text.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            text = "http://" + text;
        if (Uri.TryCreate(text, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
            Browser.Source = uri;
        else
            MessageBox.Show("Укажите корректный HTTP/HTTPS адрес панели.", "NOVA VPN",
                MessageBoxButton.OK, MessageBoxImage.Warning);
    }

    private void UpdateButtons()
    {
        BackButton.IsEnabled = Browser.CanGoBack;
        ForwardButton.IsEnabled = Browser.CanGoForward;
        AddressBox.Text = Browser.Source?.ToString() ?? AddressBox.Text;
    }

    private void Back_Click(object sender, RoutedEventArgs e) { if (Browser.CanGoBack) Browser.GoBack(); }
    private void Forward_Click(object sender, RoutedEventArgs e) { if (Browser.CanGoForward) Browser.GoForward(); }
    private void Reload_Click(object sender, RoutedEventArgs e) => Browser.Reload();
    private void Open_Click(object sender, RoutedEventArgs e) => Navigate();
    private void Settings_Click(object sender, RoutedEventArgs e) =>
        MessageBox.Show("Адрес панели можно изменить в строке сверху. Профили NOVA хранятся в AppData.",
            "NOVA VPN", MessageBoxButton.OK, MessageBoxImage.Information);

    private void Import_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog {
            Title = "Импорт профиля NOVA VPN",
            Filter = "VPN конфиги|*.conf;*.ovpn|AmneziaWG 3.1|*.conf|OpenVPN|*.ovpn|Все файлы|*.*",
            Multiselect = true
        };
        if (dialog.ShowDialog() == true) ImportFiles(dialog.FileNames);
    }

    private void OpenProfiles_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(ProfilesDir);
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo {
            FileName = ProfilesDir, UseShellExecute = true
        });
    }

    private void Window_Drop(object sender, DragEventArgs e)
    {
        if (!e.Data.GetDataPresent(DataFormats.FileDrop)) return;
        var files = (string[])e.Data.GetData(DataFormats.FileDrop)!;
        ImportFiles(files);
    }

    private void ImportFiles(IEnumerable<string> files)
    {
        var imported = new List<string>();
        var skipped = new List<string>();
        foreach (var source in files)
        {
            try
            {
                var name = Path.GetFileName(source);
                var ext = Path.GetExtension(source).ToLowerInvariant();
                var content = File.ReadAllText(source);
                var protocol = DetectProtocol(name, content);
                if (protocol == null) { skipped.Add(name); continue; }

                var safe = string.Concat(Path.GetFileNameWithoutExtension(name)
                    .Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch));
                if (string.IsNullOrWhiteSpace(safe)) safe = "NOVA-profile";
                var target = Path.Combine(ProfilesDir, $"{safe}.{(protocol == "awg" ? "conf" : "ovpn")}");
                File.Copy(source, target, true);

                var host = protocol == "awg" ? ParseAwgHost(content) : ParseOpenVpnHost(content);
                var port = protocol == "awg" ? ParseAwgPort(content) : ParseOpenVpnPort(content);
                imported.Add($"{name} → {(protocol == "awg" ? "AWG 3.1" : "OpenVPN")} • {host}:{port}");
            }
            catch { skipped.Add(Path.GetFileName(source)); }
        }

        if (imported.Count > 0)
        {
            ImportStatus.Text = $"Импортировано: {imported.Count}. " + string.Join(" | ", imported);
            MessageBox.Show(string.Join(Environment.NewLine, imported) +
                (skipped.Count > 0 ? Environment.NewLine + Environment.NewLine + "Пропущено: " + string.Join(", ", skipped) : ""),
                "NOVA VPN — импорт", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        else if (skipped.Count > 0)
            MessageBox.Show("Не найдено подходящих конфигов .conf AWG 3.1 или .ovpn.",
                "NOVA VPN", MessageBoxButton.OK, MessageBoxImage.Warning);
    }

    private static string? DetectProtocol(string fileName, string content)
    {
        var n = fileName.ToLowerInvariant();
        var l = content.ToLowerInvariant();
        if (n.EndsWith(".conf") ||
            (l.Contains("[interface]") && l.Contains("[peer]") &&
             (l.Contains("privatekey") || l.Contains("endpoint")))) return "awg";
        if (n.EndsWith(".ovpn") || l.Contains("dev tun") || l.Contains("<ca>") || l.Contains("remote "))
            return "ovpn";
        return null;
    }

    private static string ParseOpenVpnHost(string content)
    {
        foreach (var line in content.Split('\n'))
        {
            var p = line.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (p.Length >= 2 && p[0].Equals("remote", StringComparison.OrdinalIgnoreCase)) return p[1];
        }
        return "openvpn";
    }

    private static int ParseOpenVpnPort(string content)
    {
        foreach (var line in content.Split('\n'))
        {
            var p = line.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (p.Length >= 3 && p[0].Equals("remote", StringComparison.OrdinalIgnoreCase) &&
                int.TryParse(p[2], out var port)) return port;
        }
        return 1194;
    }

    private static string ParseAwgHost(string content)
    {
        var m = Regex.Match(content, @"(?im)^\s*Endpoint\s*=\s*(?:\[([^\]]+)\]|([^:\s]+))(?::\d+)?");
        return m.Success ? (m.Groups[1].Success ? m.Groups[1].Value : m.Groups[2].Value) : "amneziawg";
    }

    private static int ParseAwgPort(string content)
    {
        var m = Regex.Match(content, @"(?im)^\s*Endpoint\s*=\s*(?:\[[^\]]+\]|[^:\s]+):(?<port>\d+)");
        return m.Success && int.TryParse(m.Groups["port"].Value, out var port) ? port : 51820;
    }
}
