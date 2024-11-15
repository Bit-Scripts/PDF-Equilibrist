cmake_minimum_required(VERSION 3.10)
project(PDFEquilibrist)

# Activer le mode C++17 ou supérieur
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Inclure le dossier "src" pour nos fichiers sources
add_subdirectory(src)

# Ajouter les dépendances de la bibliothèque Poppler (et Qt si nécessaire) plus tard
# find_package(Poppler REQUIRED)
# find_package(Qt5 COMPONENTS Widgets REQUIRED) # Exemple pour Qt, à adapter

