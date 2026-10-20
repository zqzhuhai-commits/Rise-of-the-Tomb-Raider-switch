#pragma once

#include <filesystem>
#include <memory>
#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/rex_app.h>

// Initial runtime integration, pending full SDK/NVK compilation and device
// testing. This uses the SDK graphics backend as a compatibility baseline;
// it makes no assertion about acceptable Switch performance.
class RottrApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& context) {
    return std::unique_ptr<rex::ui::WindowedApp>(
        new RottrApp(context, "rottr-switch", PPCImageConfig));
  }

  void OnPostInitLogging() override {
    if (!rex::cvar::HasNonDefaultValue("gpu_plugin")) {
      rex::cvar::SetFlagByName("gpu_plugin", "xenos");
    }
  }

  void OnConfigurePaths(rex::PathConfig& paths) override {
    if (!paths.game_data_root.empty()) return;
    paths.game_data_root = rex::filesystem::GetExecutableFolder() / "game";
  }
};
