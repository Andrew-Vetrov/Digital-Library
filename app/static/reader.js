import './view.js'
import { createTOCView } from './tree.js'
import { createMenu } from './menu.js'
import { Overlayer } from './overlayer.js'

const getCSS = ({ spacing, justify, hyphenate }) => `
    @namespace epub "http://www.idpf.org/2007/ops";
    html {
        color-scheme: light dark;
    }
    /* https://github.com/whatwg/html/issues/5426 */
    @media (prefers-color-scheme: dark) {
        a:link {
            color: lightblue;
        }
    }
    p, li, blockquote, dd {
        line-height: ${spacing};
        text-align: ${justify ? 'justify' : 'start'};
        -webkit-hyphens: ${hyphenate ? 'auto' : 'manual'};
        hyphens: ${hyphenate ? 'auto' : 'manual'};
        -webkit-hyphenate-limit-before: 3;
        -webkit-hyphenate-limit-after: 2;
        -webkit-hyphenate-limit-lines: 2;
        hanging-punctuation: allow-end last;
        widows: 2;
    }
    /* prevent the above from overriding the align attribute */
    [align="left"] { text-align: left; }
    [align="right"] { text-align: right; }
    [align="center"] { text-align: center; }
    [align="justify"] { text-align: justify; }

    pre {
        white-space: pre-wrap !important;
    }
    aside[epub|type~="endnote"],
    aside[epub|type~="footnote"],
    aside[epub|type~="note"],
    aside[epub|type~="rearnote"] {
        display: none;
    }
`

const $ = document.querySelector.bind(document)

const locales = 'en'
const percentFormat = new Intl.NumberFormat(locales, { style: 'percent' })
const listFormat = new Intl.ListFormat(locales, { style: 'short', type: 'conjunction' })

const formatLanguageMap = x => {
    if (!x) return ''
    if (typeof x === 'string') return x
    const keys = Object.keys(x)
    return x[keys[0]]
}

const formatOneContributor = contributor => typeof contributor === 'string'
    ? contributor : formatLanguageMap(contributor?.name)

const formatContributor = contributor => Array.isArray(contributor)
    ? listFormat.format(contributor.map(formatOneContributor))
    : formatOneContributor(contributor)

class Reader {
    #bookId = null
    #lastSaveTime = 0
    #saveTimeout = null
    #isSaving = false
    #minSaveInterval = 2000
    
    #tocView
    style = {
        spacing: 1.4,
        justify: true,
        hyphenate: true,
    }
    annotations = new Map()
    annotationsByValue = new Map()
    closeSideBar() {
        $('#dimming-overlay').classList.remove('show')
        $('#side-bar').classList.remove('show')
    }
    constructor() {
        $('#side-bar-button').addEventListener('click', () => {
            $('#dimming-overlay').classList.add('show')
            $('#side-bar').classList.add('show')
        })
        $('#dimming-overlay').addEventListener('click', () => this.closeSideBar())
        this.#bookId = this.#extractBookId()
        this.setupSidebarTabs();
        //this.addNoteControls();
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.saveCurrentPosition()
            }
        })
        document.getElementById("add-bookmark-button")
        .addEventListener("click", () => this.addBookmark());
        document.getElementById("add-note-button")
        .addEventListener("click", () => this.createNote());
        
        
    }

    setupSidebarTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.dataset.tab;
                
                // Убираем активный класс у всех кнопок и контента
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Добавляем активный класс текущей кнопке и соответствующему контенту
                button.classList.add('active');
                document.getElementById(`${tabId}-tab`).classList.add('active');
                
                // При переключении на заметки или закладки, загружаем их если нужно
                if (tabId === 'notes') {
                    this.loadNotes();
                } else if (tabId === 'bookmarks') {
                    this.loadBookmarks();
                }
            });
        });
    }
    showNotePopup(note) {
        const popup = document.createElement('div')
        popup.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            z-index: 10001;
            min-width: 300px;
            max-width: 500px;
        `
        
        popup.innerHTML = `
            <h3 style="margin: 0 0 10px 0;">${note.title}</h3>
            <div style="color: #666; font-size: 14px; margin-bottom: 15px;">
                Романкин, Данил Романкин
            </div>
            <div style="margin-bottom: 15px; padding: 10px; background: #f9f9f9; border-radius: 4px;">
                <strong>Выделенный текст:</strong><br>
                "${note.selected_text || ''}"
            </div>
            <div style="margin-bottom: 20px;">
                ${note.text || ''}
            </div>
            <div style="display: flex; justify-content: flex-end;">
                <button id="close-note-popup" style="
                    padding: 8px 16px;
                    background: #666;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                ">Закрыть</button>
            </div>
        `
        
        document.body.appendChild(popup)
        
        popup.querySelector('#close-note-popup').addEventListener('click', () => {
            document.body.removeChild(popup)
        })
        
        // Закрытие по клику вне попапа
        setTimeout(() => {
            const closeHandler = (e) => {
                if (!popup.contains(e.target)) {
                    document.body.removeChild(popup)
                    document.removeEventListener('click', closeHandler)
                }
            }
            document.addEventListener('click', closeHandler)
        }, 100)
    }
    addNoteControls() {
        const noteButton = document.createElement('button')
        noteButton.id = 'add-note-button'
        noteButton.innerHTML = '📝 Заметка'
        noteButton.style.cssText = `
            position: fixed;
            bottom: 80px;  // Поднял выше, чтобы не мешало закладкам
            right: 20px;
            padding: 10px 15px;
            background: #FF9800;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            z-index: 9999;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 14px;
        `
        
        noteButton.addEventListener('click', async () => {
            if (!this.view?.lastLocation?.cfi) {
                alert('Выберите текст для заметки')
                return
            }
            
            const selection = window.getSelection()
            const selectedText = selection.toString().trim()
            
            if (!selectedText) {
                alert('Выделите текст для заметки')
                return
            }
            
            const noteText = prompt('Введите текст заметки:', selectedText)
            if (noteText) {
                await this.view.addNote(this.view.lastLocation.cfi, noteText)
            }
        })
        
        document.body.appendChild(noteButton)
    }
    #extractBookId() {
        // Вариант 1: Из data-атрибута
        const appElement = document.getElementById('app')
        if (appElement?.dataset.bookId) {
            return parseInt(appElement.dataset.bookId)
        }
        
        
        console.error("ERROR PARSING BOOKID")
        return null // Для локальных файлов без book_id
    }

    async #restoreFromSavedPosition(savedData) {
    if (!savedData?.loc) return
    
    try {
        if (this.view.convertLocToPosition) {
            const position = this.view.convertLocToPosition(
                savedData.loc,
                savedData.location_total
            )
            
            if (position.index !== undefined) {
                await this.view.goTo(position)
                console.log(`Restored to Loc ${savedData.loc}, section ${position.index}`)
                return
            }
        }
        
        // Fallback: используем fraction если есть
        if (savedData.fraction !== undefined) {
            await this.view.goToFraction(savedData.fraction)
            console.log(`Restored to fraction ${savedData.fraction} (Loc ${savedData.loc})`)
        }
        
    } catch (e) {
        console.error('Failed to restore:', e)
    }
}
    
    
    
    #onRelocate({ detail }) {
    const { fraction } = detail  // ← ТОЛЬКО ЭТО берем!
    
    // Сохраняем ТОЛЬКО fraction
    if (this.#bookId) {
        if (this.#saveTimeout) clearTimeout(this.#saveTimeout)
        
        this.#saveTimeout = setTimeout(() => {
            this.#saveFraction(fraction)  // ← вызываем с fraction
        }, 1000)
    }

    // UI обновляем тоже fraction
    const percent = percentFormat.format(fraction)
    const slider = $('#progress-slider')
    slider.style.visibility = 'visible'
    slider.value = fraction
    slider.title = `${percent}`
}
async #saveFraction(fraction) {
    const data = {
        loc: fraction,  // ← ТОЛЬКО ЭТО отправляем!
        //saved_at: new Date().toISOString()
    }
    if (fraction == 1.0) {
        alert("Данил Ромашка вами доволен")
    }
    await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)  // ← {fraction: 0.5432}
    })
    
    console.log(`Fraction saved: ${fraction}`)
}
    

async addBookmark() {
    if (!this.view?.lastLocation || !this.#bookId) return
    
    this.view.goLeft()
    this.view.style.opacity = '0'
    this.view.style.pointerEvents = 'none'

    this.view.goLeft()
    await new Promise(r => setTimeout(r, 1000))
    const pos = this.view.lastLocation.fraction
    await new Promise(r => setTimeout(r, 30))
    this.view.goRight()
    await new Promise(r => setTimeout(r, 30))
    const danil=this.view.lastLocation.fraction
        //const pos = this.view.lastLocation.fraction
        console.log("pos = "+pos)
    this.view.style.opacity = '1'
    this.view.style.pointerEvents = 'auto'


    const title = prompt("Название закладки:", "Моя закладка")
    if (!title) return
    await fetch(`http://localhost:3000/bookmarks/${this.#bookId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, position: pos })
    })
    
    alert("Закладка сохранена!")
    this.loadBookmarks()
}

async loadBookmarks() {
    if (!this.#bookId) return

    const response = await fetch(`http://localhost:3000/bookmarks/${this.#bookId}`)
    const bookmarks = await response.json()

    const container = document.getElementById("bookmark-list")
    if (!container) return
    
    container.innerHTML = ""

    if (bookmarks.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет закладок</div>'
        return
    }

    bookmarks.forEach(b => {
        const item = document.createElement("div")
        item.className = "bookmark-item"
        item.innerHTML = `
            <div class="bookmark-header">
                <strong>${b.title || 'Закладка'}</strong>
                <span class="bookmark-position">${Math.round(b.position * 100)}%</span>
            </div>
            <div class="bookmark-actions">
                <button data-pos="${b.position}" data-id="${b.id}" class="jump">Перейти</button>
                <button data-id="${b.id}" class="del">❌</button>
            </div>
        `
        container.appendChild(item)
    })

    container.addEventListener("click", e => {
        if (e.target.classList.contains("jump")) {
            const pos = parseFloat(e.target.dataset.pos)
            this.view.goToFraction(pos)
            this.closeSideBar()
        }
        if (e.target.classList.contains("del")) {
            this.deleteBookmark(e.target.dataset.id)
        }
    })
}

async deleteBookmark(id) {
    await fetch(`http://localhost:3000/bookmarks/${id}`, {
        method: "DELETE"
    })

    this.loadBookmarks()
}

















    #schedulePositionSave(positionData) {
        // Отменяем предыдущий таймер
        if (this.#saveTimeout) {
            clearTimeout(this.#saveTimeout)
        }
        
        // Дебаунс: сохраняем через 1 секунду после последнего изменения
        this.#saveTimeout = setTimeout(() => {
            this.#savePositionToServer(positionData)
        }, 1000)
    }
    
    async #savePositionToServer(positionData) {
        if (!this.#bookId || this.#isSaving) return
        
        // Проверяем частоту сохранений
        const now = Date.now()
        if (now - this.#lastSaveTime < this.#minSaveInterval) {
            return // Слишком часто
        }
        
        this.#isSaving = true
        
        try {
            const data = {
                loc: positionData.loc,
                location_current: positionData.loc,
                location_total: positionData.location_total,
                fraction: positionData.fraction,
                cfi: positionData.cfi,
                section_index: positionData.section_index,
                saved_at: new Date().toISOString(),
                reason: positionData.reason || 'auto_save'
            }
            
            // Удаляем пустые поля
            Object.keys(data).forEach(key => {
                if (data[key] === undefined || data[key] === null) {
                    delete data[key]
                }
            })
            
            // Используем sendBeacon для надежного сохранения
            const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
            const success = navigator.sendBeacon?.(
                `http://localhost:3000/reading_progress/${this.#bookId}`,
                blob
            )
            
            if (!success) {
                // Fallback на обычный fetch
                await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                    keepalive: true
                })
            }
            
            this.#lastSaveTime = Date.now()
            console.log(`Position saved: Loc ${data.loc}`)
            
        } catch (e) {
            console.error('Failed to save position:', e)
        
        } finally {
            this.#isSaving = false
        }
    }
    
    #saveToLocalStorage(positionData) {
        try {
            const key = `book_position_${this.#bookId}`
            localStorage.setItem(key, JSON.stringify({
                ...positionData,
                saved_at: new Date().toISOString(),
                is_backup: true
            }))
        } catch (e) {
            console.error('Failed to save to localStorage:', e)
        }
    }
    


 async createNote() {
    if (!this.view?.lastLocation || !this.#bookId) return
    // Получаем выделенный текст
    const selectedText = this.getSelectedText()
    console.log("Выделенный текст:", selectedText)
    console.log(selectedText.length)
    if (!selectedText) {
        alert("Выделите текст для заметки!")
        return
    }
    if (selectedText.length > 3000) {
        return
    }
    // Тот же трюк для позиционирования
    /*this.view.goLeft()
    this.view.style.opacity = '0'
    this.view.style.pointerEvents = 'none'

    this.view.goLeft()
    await new Promise(r => setTimeout(r, 1000))*/
    const pos = this.view.lastLocation.fraction
    /*await new Promise(r => setTimeout(r, 30))
    this.view.goRight()
    await new Promise(r => setTimeout(r, 30))
    const danil = this.view.lastLocation.fraction
    console.log("pos = " + pos)
    
    this.view.style.opacity = '1'
    this.view.style.pointerEvents = 'auto'*/

    
    
    // Получаем CFI ВЫДЕЛЕНИЯ, а не страницы
    const selectionCFI = this.getSelectionCFI()
    console.log("CFI выделения:", selectionCFI)
    
    // Используем CFI выделения если есть, иначе позицию страницы
    const cfi = selectionCFI || this.view.lastLocation.cfi
    
    // Только название - текст заметки будет выделенный текст
    const title = prompt("Название заметки:", selectedText.substring(0, 30))
    if (!title) return
    
    // Текст заметки = выделенный текст
    const noteText = selectedText
    
    console.log("Отправляю заметку...")
    console.log("Title:", title)
    console.log("Text (выделенный):", noteText)
    console.log("CFI:", cfi)
    console.log("Position:", pos)
    
    try {
        const response = await fetch(`http://localhost:3000/notes/${this.#bookId}`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ 
                title, 
                position: pos, 
                text: noteText,
                selected_text: selectedText,
                cfi: cfi,
                color: 'yellow' 
            })
        })
        
        if (!response.ok) {
            const errorText = await response.text()
            console.error('Ошибка сервера:', response.status, errorText)
            alert(`Ошибка сервера: ${response.status}`)
            return
        }
        
        const createdNote = await response.json()
        console.log("Создана заметка:", createdNote)
        
        if (createdNote.id && this.view?.addNoteHighlight) {
            console.log("Добавляю выделение...")
            await this.view.addNoteHighlight(createdNote)
        }
        
        // Обновляем список
        await this.loadNotes()
        
        alert("✅ Заметка сохранена!")
        
    } catch (error) {
        console.error("Ошибка создания заметки:", error)
        alert(`Ошибка: ${error.message}`)
    }
}

getSelectedText() {
    console.log('=== getSelectedText ===')
    
    // Способ 1: Пробуем получить из всех iframe
    const contents = this.view?.renderer?.getContents()
    if (contents && contents.length > 0) {
        for (const content of contents) {
            if (content.doc) {
                const selection = content.doc.getSelection()
                console.log('Selection в документе:', selection)
                if (selection && selection.rangeCount > 0) {
                    const selectedText = selection.toString().trim()
                    console.log('Выделенный текст из iframe:', selectedText)
                    if (selectedText) {
                        return selectedText
                    }
                }
            }
        }
    }
    
    // Способ 2: Пробуем из window (если выделение вне iframe)
    const windowSelection = window.getSelection()
    console.log('Selection в window:', windowSelection)
    if (windowSelection && windowSelection.rangeCount > 0) {
        const selectedText = windowSelection.toString().trim()
        console.log('Выделенный текст из window:', selectedText)
        if (selectedText) {
            return selectedText
        }
    }
    
    console.log('Не найдено выделенного текста')
    return ''
}

// Метод для получения текущего выделения (Range)
getCurrentSelection() {
    const contents = this.view?.renderer?.getContents()
    if (contents && contents.length > 0) {
        for (const content of contents) {
            if (content.doc) {
                const selection = content.doc.getSelection()
                if (selection && selection.rangeCount > 0) {
                    return selection.getRangeAt(0)
                }
            }
        }
    }
    
    const windowSelection = window.getSelection()
    if (windowSelection && windowSelection.rangeCount > 0) {
        return windowSelection.getRangeAt(0)
    }
    
    return null
}

// Метод для получения CFI выделения
getSelectionCFI() {
    const contents = this.view?.renderer?.getContents()
    if (!contents || contents.length === 0) {
        console.log('Нет загруженных страниц')
        return null
    }
    
    for (const content of contents) {
        if (content.doc) {
            const selection = content.doc.getSelection()
            if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
                try {
                    const range = selection.getRangeAt(0)
                    console.log('Нашел выделение в документе')
                    console.log('Range:', range.toString())
                    
                    // Получаем CFI для этого range
                    const cfi = this.view.getCFI(content.index, range)
                    console.log('CFI выделения:', cfi)
                    return cfi
                } catch (e) {
                    console.error('Ошибка получения CFI выделения:', e)
                }
            }
        }
    }
    
    console.log('Не найдено активного выделения')
    return null
}

async loadNotes() {
    if (!this.#bookId) return

    const response = await fetch(`http://localhost:3000/notes/${this.#bookId}`)
    
    if (!response.ok) {
        console.error("Failed to load notes")
        return
    }
    
    const notes = await response.json()
    console.log('Загружено заметок:', notes.length)

    
    // ЗАГРУЖАЕМ ЗАМЕТКИ В VIEW (для подсветки в тексте)
    if (this.view) {
        this.view.loadNotesForBook(this.#bookId, notes)
    }
    
    const container = document.getElementById("notes-list")
    if (!container) return
    
    if (notes.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет заметок</div>'
        return
    }

    container.innerHTML = ""
    notes.forEach(n => {
        const item = document.createElement("div")
        item.className = "note-item"
        item.innerHTML = `
            <div class="note-header">
                <strong>${n.title}</strong>
                <span class="note-position">${Math.round(n.position * 100)}%</span>
            </div>
            <div class="note-preview">${n.selected_text || n.text?.substring(0, 50) || ''}...</div>
            <div class="note-actions">
                <button data-pos="${n.position}" data-id="${n.id}" data-cfi="${n.cfi || ''}" class="jump">Перейти</button>
                <button data-id="${n.id}" class="del">❌</button>
            </div>
        `
        container.appendChild(item)
    })

    container.addEventListener("click", e => {
        if (e.target.classList.contains("jump")) {
            const pos = parseFloat(e.target.dataset.pos)
            const noteId = e.target.dataset.id
            const cfi = e.target.dataset.cfi
            
            if (cfi) {
                this.view.goTo(cfi)
            } else if (pos) {
                this.view.goToFraction(pos)
            }
            this.closeSideBar()
        }
        if (e.target.classList.contains("del")) {
            this.deleteNote(e.target.dataset.id)
        }
    })

    return notes
}

async getNotesData() {
    if (!this.#bookId) return []
    
    try {
        const response = await fetch(`http://localhost:3000/notes/${this.#bookId}`)
        if (!response.ok) return []
        return await response.json()
    } catch (error) {
        console.error('Ошибка загрузки заметок:', error)
        return []
    }
}

async deleteNote(id) {
    await fetch(`http://localhost:3000/notes/${id}`, {
        method: "DELETE"
    })

    // УДАЛЯЕМ ВЫДЕЛЕНИЕ ИЗ VIEW
    this.view.removeNoteHighlight(parseInt(id))
    
    // ПЕРЕЗАГРУЖАЕМ СПИСОК
    await this.loadNotes()
}




    #savePosition(reason) {
        if (!this.view?.lastLocation || !this.#bookId) return
        
        const position = this.view.lastLocation
        
        this.#savePositionToServer({
            loc: position.location?.current,
            location_total: position.location?.total,
            fraction: position.fraction,
            cfi: position.cfi,
            section_index: position.section?.current,
            reason: reason
        })
    }

    async open(file) {
        let savedLoc = null
        await this.loadBookmarks()
        await this.loadNotes()
        
        if (this.#bookId) {
            try {
                const response = await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`)
                if (response.ok) {
                    const data = await response.json()
                    if (data.loc !== null && data.loc !== undefined) {
                        savedLoc = data.loc
                        console.log(`Loaded saved Loc: ${savedLoc}`)
                    }
                }
            } catch (e) {
                console.error('Failed to load saved position:', e)
            }
        }
        this.view = document.createElement('diglib-view')
        document.body.append(this.view)
        
        this.view.addEventListener('load', async () => {
            console.log('Книга загружена, загружаю заметки...')
            
            if (this.#bookId) {
                // Ждем немного чтобы view успел инициализироваться
                
                setTimeout(async () => {
                    const notes = await this.loadNotes()
                    const notesData = await this.getNotesData()
                    console.log('Загружено заметок из БД:', notes.length)
                    
                    if (notes.length > 0 && this.view.loadNotesForBook) {
                        // Загружаем заметки в view
                        await this.view.loadNotesForBook(this.#bookId, notesData)
                        
                        // Принудительно перерисовываем заметки на текущей странице
                        if (this.view.renderer?.getContents) {
                            const contents = this.view.renderer.getContents()
                            if (contents.length > 0) {
                                const { index, doc } = contents[0]
                                if (this.view.renderNotesForPage) {
                                    this.view.renderNotesForPage(index, doc)
                                }
                            }
                        }
                    }
                }, 1000)
            }
        })
        await this.view.open(file)
        this.view.addEventListener('show-note', (e) => {
            const { note } = e.detail
            this.showNotePopup(note)
        })
        this.view.addEventListener('load', this.#onLoad.bind(this))
        this.view.addEventListener('relocate', this.#onRelocate.bind(this))

        const { book } = this.view
        book.transformTarget?.addEventListener('data', ({ detail }) => {
            detail.data = Promise.resolve(detail.data).catch(e => {
                console.error(new Error(`Failed to load ${detail.name}`, { cause: e }))
                return ''
            })
        })
        this.view.renderer.setStyles?.(getCSS(this.style))
        this.view.renderer.next()

        $('#header-bar').style.visibility = 'visible'
        $('#nav-bar').style.visibility = 'visible'
        $('#left-button').addEventListener('click', () => this.view.goLeft())
        $('#right-button').addEventListener('click', () => this.view.goRight())

        const slider = $('#progress-slider')
        slider.dir = book.dir
        slider.addEventListener('input', e =>
            this.view.goToFraction(parseFloat(e.target.value)))
        for (const fraction of this.view.getSectionFractions()) {
            const option = document.createElement('option')
            option.value = fraction
            $('#tick-marks').append(option)
        }

        document.addEventListener('keydown', this.#handleKeydown.bind(this))

        const title = formatLanguageMap(book.metadata?.title) || 'Untitled Book'
        document.title = title
        $('#side-bar-title').innerText = title
        $('#side-bar-author').innerText = formatContributor(book.metadata?.author)
        Promise.resolve(book.getCover?.())?.then(blob =>
            blob ? $('#side-bar-cover').src = URL.createObjectURL(blob) : null)

        const toc = book.toc
        if (toc) {
            this.#tocView = createTOCView(toc, href => {
                this.view.goTo(href).catch(e => console.error(e))
                this.closeSideBar()
            })
            $('#toc-view').append(this.#tocView.element)
        }

        // load and show highlights embedded in the file by Calibre
        const bookmarks = await book.getCalibreBookmarks?.()
        if (bookmarks) {
            const { fromCalibreHighlight } = await import('./epubcfi.js')
            for (const obj of bookmarks) {
                if (obj.type === 'highlight') {
                    const value = fromCalibreHighlight(obj)
                    const color = obj.style.which
                    const note = obj.notes
                    const annotation = { value, color, note }
                    const list = this.annotations.get(obj.spine_index)
                    if (list) list.push(annotation)
                    else this.annotations.set(obj.spine_index, [annotation])
                    this.annotationsByValue.set(value, annotation)
                }
            }
            this.view.addEventListener('create-overlay', e => {
                const { index } = e.detail
                const list = this.annotations.get(index)
                if (list) for (const annotation of list)
                    this.view.addAnnotation(annotation)
            })
            this.view.addEventListener('draw-annotation', e => {
                const { draw, annotation } = e.detail
                const { color } = annotation
                draw(Overlayer.highlight, { color })
            })
            this.view.addEventListener('show-annotation', e => {
                const annotation = this.annotationsByValue.get(e.detail.value)
                if (annotation.note) alert(annotation.note)
            })
        }

         if (savedLoc !== null) {
            // Ждем немного пока книга загрузится
            setTimeout(() => {
                this.#restorePosition(savedLoc)
            }, 500)
        } else {
            this.view.renderer.next()
        }
    }

    async #restorePosition(fraction) {
        // 1. Скрываем
    this.view.style.opacity = '0'
    
    // 2. Ждем загрузки
    await new Promise(r => setTimeout(r, 500))
    
    // 3. Переходим
    await this.view.goToFraction(fraction)
    
    // 4. Форсируем рендер
    //this.view.renderer?.previous?.() // туда-сюда

    // 5. Ждем
    await new Promise(r => setTimeout(r, 300))
    
    // 6. Показываем
    this.view.style.opacity = '1'
    if (fraction != 1.0){this.view.goLeft()}
    
    // 7. Еще раз уточняем (иногда помогает)

    setTimeout(() => {this.view.goToFraction(fraction)},100)
    // setTimeout(() => {
    //     this.view.goToFraction(fraction + 0.001).then(() => {
    //         this.view.goToFraction(fraction - 0.001)
    //     })
    // }, 100)
    }

    #handleKeydown(event) {
        const k = event.key
        if (k === 'ArrowLeft' || k === 'h') this.view.goLeft()
        else if(k === 'ArrowRight' || k === 'l') this.view.goRight()
    }
    #onLoad({ detail: { doc } }) {
        doc.addEventListener('keydown', this.#handleKeydown.bind(this))
    }
    

     async #saveLoc(locNumber) {
        return
        if (!this.#bookId) return
        
        try {
            const response = await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ loc: locNumber })
            })
            
            if (response.ok) {
                console.log(`Loc ${locNumber} saved successfully`)
            } else {
                console.error(`Failed to save Loc ${locNumber}: ${response.status}`)
            }
        } catch (e) {
            console.error('Error saving Loc:', e)
        }
    }

    saveCurrentPosition() {
        if (!this.view?.lastLocation?.location?.current || !this.#bookId) return
        this.#saveLoc(this.view.lastLocation.location.current)
    }
}

const open = async file => {
    const reader = new Reader()
    globalThis.reader = reader
    await reader.open(file)
}



const bookUrl = document.getElementById("app").dataset.bookUrl;
if (bookUrl) open(bookUrl).catch(e => console.error(e))
else dropTarget.style.visibility = 'visible'