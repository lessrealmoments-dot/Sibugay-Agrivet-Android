# printer-release.aar

COPY THE FILE HERE BEFORE BUILDING:

Place `printer-release.aar` (from the Senraise H10P SDK package) into this directory:
  android/app/libs/printer-release.aar

This file is NOT committed to the repository (binary files excluded via .gitignore).
You must manually copy it here before opening the project in Android Studio.

Why this directory:
  build.gradle references it as:
    implementation(name: 'printer-release', ext: 'aar')
  with a flatDir repository pointing to 'libs'.
