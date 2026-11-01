// Financeiro: app nativo do macOS (Swift + WebKit, só frameworks da Apple).
// Abre numa janela própria (WebKit), liga o servidor local ao abrir e desliga ao fechar.
// Nada sai do Mac: só carrega http://localhost:47821.
import Cocoa
import WebKit

let PORT = 47821
let HOME = FileManager.default.homeDirectoryForCurrentUser.path
// Pasta da instalação (relativa à pasta de usuário). O instalador grava em Info.plist.
let PASTA_REL = (Bundle.main.object(forInfoDictionaryKey: "FinanceiroPasta") as? String) ?? "Library/Application Support/Financeiro"
let BASE = HOME + "/" + PASTA_REL
let PAINEL = URL(string: "http://localhost:\(PORT)/")!
let SAUDE = URL(string: "http://localhost:\(PORT)/api/saude")!

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()  // não guarda cache nem histórico
        web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self
        web.navigationDelegate = self
        web.loadHTMLString(Self.aviso("Ligando o painel…"), baseURL: nil)

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 880),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Financeiro"
        window.minSize = NSSize(width: 420, height: 500)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("FinanceiroJanela")
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        checarSaude { ok in
            if ok { self.web.load(URLRequest(url: PAINEL)) } else { self.ligarServidor(); self.esperar(0) }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        if let s = server, s.isRunning { s.terminate(); s.waitUntilExit() }
    }

    // MARK: servidor local
    func ligarServidor() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: BASE + "/venv/bin/python3")
        p.arguments = ["-I", "server.py"]
        p.currentDirectoryURL = URL(fileURLWithPath: BASE + "/app")
        var env = ProcessInfo.processInfo.environment
        env["FATURAS_PORT"] = String(PORT)
        env["FATURAS_DATA"] = BASE + "/dados"
        p.environment = env
        let log = BASE + "/dados/servidor.log"
        FileManager.default.createFile(atPath: log, contents: nil, attributes: [.posixPermissions: 0o600])
        if let h = FileHandle(forWritingAtPath: log) { p.standardOutput = h; p.standardError = h }
        do { try p.run(); server = p } catch {
            web.loadHTMLString(Self.aviso("Não consegui ligar o painel: \(error.localizedDescription)"), baseURL: nil)
        }
    }

    func checarSaude(_ done: @escaping (Bool) -> Void) {
        var req = URLRequest(url: SAUDE); req.timeoutInterval = 1
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            let ok = (resp as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async { done(ok) }
        }.resume()
    }

    func esperar(_ n: Int) {
        if n > 60 {
            web.loadHTMLString(Self.aviso("O painel não respondeu. Veja ~/\(PASTA_REL)/dados/servidor.log"), baseURL: nil)
            return
        }
        checarSaude { ok in
            if ok { self.web.load(URLRequest(url: PAINEL)) }
            else { DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.esperar(n + 1) } }
        }
    }

    static func aviso(_ t: String) -> String {
        "<html><body style='font:15px -apple-system;color:#888;display:flex;height:100vh;margin:0;align-items:center;justify-content:center;background:transparent'>\(t)</body></html>"
    }

    // MARK: WebKit: escolher arquivos, alertas, links
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.message = "Escolha as faturas em PDF"
        panel.beginSheetModal(for: window) { r in completionHandler(r == .OK ? panel.urls : nil) }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = message
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancelar")
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn) }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message
        a.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = action.request.url, let h = u.host, h != "localhost", h != "127.0.0.1" {
            NSWorkspace.shared.open(u)  // qualquer link de fora abre no navegador
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }

    // MARK: menu
    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Ocultar Financeiro", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Encerrar Financeiro", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Editar")
        edit.addItem(withTitle: "Desfazer", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Refazer", action: Selector(("redo:")), keyEquivalent: "Z")
        edit.addItem(.separator())
        edit.addItem(withTitle: "Recortar", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Colar", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Selecionar Tudo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit

        let viewItem = NSMenuItem(); main.addItem(viewItem)
        let view = NSMenu(title: "Visualizar")
        view.addItem(withTitle: "Recarregar", action: #selector(recarregar), keyEquivalent: "r")
        viewItem.submenu = view

        let winItem = NSMenuItem(); main.addItem(winItem)
        let win = NSMenu(title: "Janela")
        win.addItem(withTitle: "Minimizar", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        win.addItem(withTitle: "Fechar", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        winItem.submenu = win
        NSApp.windowsMenu = win
        NSApp.mainMenu = main
    }

    @objc func recarregar() { web.reload() }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
