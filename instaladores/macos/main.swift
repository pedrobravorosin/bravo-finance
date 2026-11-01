// Bravo Finance: app nativo do macOS (Swift + WebKit, só frameworks da Apple).
//
// - Traz o próprio Python dentro do app (Contents/Resources/python): não precisa
//   de ferramentas da Apple, de internet nem de nenhuma permissão especial.
// - Liga o servidor local (só 127.0.0.1, porta livre escolhida na hora) e recebe
//   dele uma chave de uso único pela saída padrão; a janela entra com essa chave.
// - A janela só navega no endereço do próprio servidor. Qualquer outro endereço
//   é recusado (não abre nem no navegador).
// - Ao fechar, o servidor desliga (a entrada padrão dele fecha junto com o app).
import Cocoa
import WebKit

let NOME = "Bravo Finance"
let RECURSOS = Bundle.main.resourceURL!
let PYTHON = RECURSOS.appendingPathComponent("python/bin/python3")
let SERVIDOR = RECURSOS.appendingPathComponent("app/server.py")
let DADOS = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
    .appendingPathComponent(NOME, isDirectory: true)

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var entrada: Pipe?
    var porta = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()  // nada fica guardado: nem cache, nem cookies
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = false
        web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self
        web.navigationDelegate = self
        web.loadHTMLString(Self.aviso("Abrindo o \(NOME)…"), baseURL: nil)

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 880),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = NOME
        window.minSize = NSSize(width: 420, height: 500)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("BravoFinanceJanela")
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        ligarServidor()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        try? entrada?.fileHandleForWriting.close()  // o servidor desliga sozinho
        if let s = server, s.isRunning {
            DispatchQueue.global().asyncAfter(deadline: .now() + 3) { if s.isRunning { s.terminate() } }
            s.waitUntilExit()
        }
    }

    // MARK: servidor local
    func ligarServidor() {
        do {
            try FileManager.default.createDirectory(at: DADOS, withIntermediateDirectories: true,
                                                    attributes: [.posixPermissions: 0o700])
        } catch {
            return falhar("Não consegui criar a pasta de dados: \(error.localizedDescription)")
        }
        let log = DADOS.appendingPathComponent("servidor.log")
        FileManager.default.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600])

        let p = Process()
        p.executableURL = PYTHON
        p.arguments = ["-I", "-s", SERVIDOR.path, "--janela"]
        p.currentDirectoryURL = SERVIDOR.deletingLastPathComponent()
        // Ambiente mínimo: nada herdado que possa mudar o comportamento do Python.
        p.environment = ["HOME": NSHomeDirectory(), "LANG": "pt_BR.UTF-8", "PATH": "/usr/bin:/bin",
                         "BRAVO_DADOS": DADOS.path]
        let entrada = Pipe(), saida = Pipe()
        p.standardInput = entrada
        p.standardOutput = saida
        p.standardError = (try? FileHandle(forWritingTo: log)) ?? FileHandle.nullDevice
        p.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                if self?.porta == 0 || proc.terminationStatus != 0 { self?.servidorParou(proc.terminationStatus) }
            }
        }
        do { try p.run() } catch { return falhar("Não consegui abrir o \(NOME): \(error.localizedDescription)") }
        server = p
        self.entrada = entrada

        // Primeira linha: "BRAVO-FINANCE <porta> <chave>" (ou "BRAVO-FINANCE OCUPADO").
        DispatchQueue.global().async {
            var dados = Data()
            let h = saida.fileHandleForReading
            while !dados.contains(0x0A) {
                let parte = h.availableData
                if parte.isEmpty { break }
                dados.append(parte)
            }
            let linha = String(decoding: dados, as: UTF8.self).split(separator: "\n").first ?? ""
            let campos = linha.split(separator: " ").map(String.init)
            DispatchQueue.main.async { self.entrar(campos) }
        }
    }

    func entrar(_ campos: [String]) {
        if campos == ["BRAVO-FINANCE", "OCUPADO"] {
            return falhar("O \(NOME) já está aberto em outra janela.")
        }
        guard campos.count == 3, campos[0] == "BRAVO-FINANCE", let p = Int(campos[1]), p > 0,
              campos[2].allSatisfy({ $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }),
              let url = URL(string: "http://127.0.0.1:\(p)/entrar?t=\(campos[2])") else {
            return falhar("O \(NOME) não conseguiu ligar. Veja o arquivo servidor.log em ~/Library/Application Support/\(NOME).")
        }
        porta = p
        web.load(URLRequest(url: url))
    }

    func servidorParou(_ status: Int32) {
        if status == 3 { return }  // já aberto: a mensagem já foi mostrada
        falhar("O \(NOME) parou de responder. Feche e abra de novo.")
    }

    func falhar(_ texto: String) {
        web.loadHTMLString(Self.aviso(texto), baseURL: nil)
    }

    static func aviso(_ t: String) -> String {
        let seguro = t.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;")
        return "<html><body style='font:15px -apple-system;color:#888;display:flex;height:100vh;margin:0;align-items:center;justify-content:center;text-align:center;padding:0 40px'>\(seguro)</body></html>"
    }

    // MARK: WebKit: só o servidor local; escolher arquivos; alertas
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = action.request.url else { return decisionHandler(.cancel) }
        if u.scheme == "about" || (u.scheme == "http" && u.host == "127.0.0.1" && u.port == porta && porta > 0) {
            return decisionHandler(.allow)
        }
        decisionHandler(.cancel)  // nada de fora: nem na janela, nem no navegador
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        nil  // sem janelas novas
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowedFileTypes = ["pdf"]
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

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = prompt
        let campo = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        a.accessoryView = campo
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancelar")
        a.beginSheetModal(for: window) { r in completionHandler(r == .alertFirstButtonReturn ? campo.stringValue : nil) }
    }

    // MARK: menu
    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Sobre o \(NOME)", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Ocultar \(NOME)", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Encerrar \(NOME)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
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
