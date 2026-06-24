# Distribute Windows builds through Microsoft Store MSIX

XMCP Manager distributes Windows production builds through Microsoft Store using MSIX packages rather than an Inno Setup installer. GitHub Actions builds the Windows executable with PyInstaller and packages it with Windows SDK `MakeAppx.exe`; the resulting MSIX remains a release candidate artifact until Store package validation passes, after which it can be attached to a draft release.
