((python-mode . ((flycheck-checker . python-mypy)))
 (nil . ((eval . (progn
                   (setq-local my-local-root (projectile-project-root))
                   (setq-local my-local-path (expand-file-name "." my-local-root))
                   (setq dap-debug-template-configurations
                         `(("Local Pytest Debug"
                            :type "python"
                            :request "attach"
                            :connect ( :host "localhost" :port 5678 )
                            :name "Local Pytest Debug"
                            :pathMappings (((:localRoot . ,my-local-path)
                                            (:remoteRoot . ,my-local-path)))))))))))
