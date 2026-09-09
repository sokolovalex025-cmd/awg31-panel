using System;
using System.Diagnostics;
using System.Windows;
namespace AWGPanel.Desktop;
public partial class MainWindow : Window
{
    public MainWindow(){InitializeComponent(); Loaded += async (_,__) => { await Browser.EnsureCoreWebView2Async(); Browser.CoreWebView2.NavigationCompleted += (_,__) => UpdateButtons(); Navigate(); };}
    void Navigate(){ if(Uri.TryCreate(AddressBox.Text.Trim(), UriKind.Absolute, out var uri) && (uri.Scheme==Uri.UriSchemeHttp || uri.Scheme==Uri.UriSchemeHttps)) Browser.Source=uri; else MessageBox.Show("Укажите корректный HTTP/HTTPS адрес панели.","AWG Panel",MessageBoxButton.OK,MessageBoxImage.Warning); }
    void UpdateButtons(){ BackButton.IsEnabled=Browser.CanGoBack; ForwardButton.IsEnabled=Browser.CanGoForward; AddressBox.Text=Browser.Source?.ToString() ?? AddressBox.Text; }
    void Back_Click(object s,RoutedEventArgs e){if(Browser.CanGoBack)Browser.GoBack();}
    void Forward_Click(object s,RoutedEventArgs e){if(Browser.CanGoForward)Browser.GoForward();}
    void Reload_Click(object s,RoutedEventArgs e){Browser.Reload();}
    void Open_Click(object s,RoutedEventArgs e){Navigate();}
    void Settings_Click(object s,RoutedEventArgs e){MessageBox.Show("Здесь можно будет добавить профиль, адрес панели и дополнительные настройки.","AWG Panel",MessageBoxButton.OK,MessageBoxImage.Information);}
}
