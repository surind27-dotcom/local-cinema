package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type VideoFile struct {
	Name   string  `json:"name"`
	Path   string  `json:"path"`
	SizeMB float64 `json:"size_mb"`
}

// Глобальные переменные для кеша
var (
	videoCache []VideoFile
	cacheMutex sync.RWMutex // Защита данных от одновременной записи/чтения
)

func scanMovies(root string) ([]VideoFile, error) {
	var videos []VideoFile
	extensions := map[string]bool{
		".mp4": true, ".mkv": true, ".avi": true, ".webm": true, ".mov": true,
	}

	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil // Пропускаем папки с ошибками доступа, чтобы не падать
		}
		if !d.IsDir() {
			ext := strings.ToLower(filepath.Ext(path))
			if extensions[ext] {
				relPath, _ := filepath.Rel(root, path)
				info, _ := d.Info()
				videos = append(videos, VideoFile{
					Name:   d.Name(),
					Path:   filepath.ToSlash(relPath),
					SizeMB: float64(info.Size()) / 1024 / 1024,
				})
			}
		}
		return nil
	})
	return videos, err
}

// Фоновая функция обновления списка файлов
func updateCachePeriodically(root string) {
	for {
		newList, err := scanMovies(root)
		if err == nil {
			cacheMutex.Lock()
			videoCache = newList
			cacheMutex.Unlock()
			// log.Println("🔄 Список файлов обновлен") // Можно раскомментировать для отладки
		}
		time.Sleep(30 * time.Second) // Спим 30 секунд. Процессор отдыхает!
	}
}

func main() {
	const movieDir = "./movies"

	if _, err := os.Stat(movieDir); os.IsNotExist(err) {
		os.Mkdir(movieDir, 0755)
	}

	// Запускаем сканер в отдельном потоке (goroutine)
	go updateCachePeriodically(movieDir)

	http.HandleFunc("/api/files", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Content-Type", "application/json")

		// Отдаем данные из памяти (очень быстро)
		cacheMutex.RLock()
		defer cacheMutex.RUnlock()

		if videoCache == nil {
			json.NewEncoder(w).Encode([]VideoFile{})
			return
		}
		json.NewEncoder(w).Encode(videoCache)
	})

	fmt.Println("Go-сервер на http://localhost:8001/api/files")
	log.Fatal(http.ListenAndServe(":8001", nil))
}
