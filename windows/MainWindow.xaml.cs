using System;
using System.Windows;
using Microsoft.Web.WebView2.Wpf;

namespace AWGPanel.Desktop;

public partial class MainWindow : Window
{
    private readonly WebView2 Browser = new();

    public MainWindow()
    {
        InitializeComponent();
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
            MessageBox.Show("Укажите корректный HTTP/HTTPS адрес панели.", "AWG Panel", MessageBoxButton.OK, MessageBoxImage.Warning);
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
    private void Settings_Click(object sender, RoutedEventArgs e) => MessageBox.Show("Адрес панели можно изменить в строке сверху.", "AWG Panel", MessageBoxButton.OK, MessageBoxImage.Information);
}
