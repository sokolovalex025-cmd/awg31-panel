import SwiftUI
import WebKit

struct ContentView: View {
    @AppStorage("panelURL") private var panelURL = "http://95.85.241.45:8080"
    @State private var showSettings = false
    @State private var reloadID = UUID()
    var body: some View {
        NavigationStack {
            PanelWebView(url: URL(string: panelURL)!)
                .id(reloadID)
                .toolbar {
                    ToolbarItemGroup(placement: .bottomBar) {
                        Button { NotificationCenter.default.post(name: .webBack, object: nil) } label: { Image(systemName: "chevron.left") }
                        Button { NotificationCenter.default.post(name: .webForward, object: nil) } label: { Image(systemName: "chevron.right") }
                        Spacer()
                        Button { reloadID = UUID() } label: { Image(systemName: "arrow.clockwise") }
                        Button { showSettings = true } label: { Image(systemName: "gearshape.fill") }
                    }
                }
                .sheet(isPresented: $showSettings) {
                    NavigationStack {
                        Form { TextField("http://IP:8080", text: $panelURL).textInputAutocapitalization(.never).autocorrectionDisabled() }
                            .navigationTitle("Адрес AWG Panel")
                            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Готово") { showSettings = false; reloadID = UUID() } } }
                    }
                }
                .navigationTitle("AWG Panel")
                .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct PanelWebView: UIViewRepresentable {
    let url: URL
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeUIView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = context.coordinator
        web.allowsBackForwardNavigationGestures = true
        web.load(URLRequest(url: url, timeoutInterval: 30))
        NotificationCenter.default.addObserver(forName: .webBack, object: nil, queue: .main) { _ in if web.canGoBack { web.goBack() } }
        NotificationCenter.default.addObserver(forName: .webForward, object: nil, queue: .main) { _ in if web.canGoForward { web.goForward() } }
        return web
    }
    func updateUIView(_ webView: WKWebView, context: Context) {}
    final class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let u = navigationAction.request.url, ["http", "https"].contains(u.scheme?.lowercased()) else { decisionHandler(.cancel); return }
            decisionHandler(.allow)
        }
    }
}

extension Notification.Name {
    static let webBack = Notification.Name("AWGWebBack")
    static let webForward = Notification.Name("AWGWebForward")
}
