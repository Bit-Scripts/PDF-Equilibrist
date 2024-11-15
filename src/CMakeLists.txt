# Inclure les fichiers sources
set(SOURCES
        main.cpp
)

# Créer l'exécutable PDF-Equilibrist à partir de ces sources
add_executable(PDFEquilibrist ${SOURCES})

# Lier les bibliothèques si nécessaires
# target_link_libraries(PDFEquilibrist PRIVATE Poppler::Poppler)
# target_link_libraries(PDFEquilibrist PRIVATE Qt5::Widgets) # Exemple pour Qt
