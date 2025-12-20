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
    #notificationStack = []
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
        
         const bookmarkBtn = document.getElementById("add-bookmark-button")
        bookmarkBtn.removeEventListener("click", this.handleBookmarkClick)
        bookmarkBtn.addEventListener("click", this.handleBookmarkClick.bind(this))
        document.getElementById("add-note-button")
            .addEventListener("click", () => this.createNote())

        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.saveCurrentPosition()
            }
        })
        
        
    }

    handleBookmarkClick() {
        this.showBookmarkCreationPopup()
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
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            z-index: 10001;
            min-width: 350px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            font-family: system-ui, sans-serif;
        `
        
        // ДОБАВЛЯЕМ КОММЕНТАРИЙ В POPUP
        const commentHTML = note.comment 
            ? `<div style="
                    margin-top: 15px;
                    padding: 12px;
                    background: #f8f9fa;
                    border-radius: 6px;
                    border-left: 4px solid #4CAF50;
                ">
                <div style="font-size: 14px; color: #666; margin-bottom: 5px;">
                    <strong>Комментарий:</strong>
                </div>
                <div style="font-size: 15px; color: #333; line-height: 1.5;">
                    ${note.comment}
                </div>
            </div>`
            : '<div style="margin-top: 15px; color: #999; font-style: italic;">Нет комментария</div>'
        
        popup.innerHTML = `
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 8px 0; color: #333; font-size: 18px;">${note.title || 'Заметка'}</h3>
                <div style="color: #666; font-size: 13px; margin-bottom: 15px;">
                    ${note.created_at ? new Date(note.created_at).toLocaleDateString('ru-RU') : ''}
                </div>
            </div>
            
            <div style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 6px;">
                <div style="font-size: 14px; color: #666; margin-bottom: 8px;">
                    <strong>Выделенный текст:</strong>
                </div>
                <div style="
                    font-size: 15px;
                    color: #333;
                    line-height: 1.6;
                    font-style: italic;
                    border-left: 3px solid #FF9800;
                    padding-left: 12px;
                    background: white;
                    padding: 12px;
                    border-radius: 4px;
                ">
                    "${note.selected_text || note.text || ''}"
                </div>
            </div>
            
            ${commentHTML}
            
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 25px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            ">
                <div style="color: #666; font-size: 13px;">
                    Позиция: ${Math.round((note.position || 0) * 100)}%
                </div>
                <div style="display: flex; gap: 10px;">
                    <button id="edit-note" style="
                        padding: 8px 16px;
                        background: #2196F3;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Редактировать</button>
                    <button id="close-note-popup" style="
                        padding: 8px 16px;
                        background: #666;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Закрыть</button>
                </div>
            </div>
        `
        
        document.body.appendChild(popup)
        
        // КНОПКА РЕДАКТИРОВАНИЯ
        popup.querySelector('#edit-note').addEventListener('click', () => {
            this.editNote(note, popup)
        })
        
        // КНОПКА ЗАКРЫТИЯ
        popup.querySelector('#close-note-popup').addEventListener('click', () => {
            document.body.removeChild(popup)
        })
        popup.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.body.removeChild(popup)
            }
            // Останавливаем всплытие
            e.stopPropagation()
        })

        // Для всех полей ввода внутри попапа:
        popup.querySelectorAll('input, textarea, button').forEach(element => {
            element.addEventListener('keydown', (e) => e.stopPropagation())
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

    

    async editNote(note, popup) {
        const newTitle = prompt("Измените название заметки:", note.title || '')
        if (newTitle === null) return // пользователь отменил
        
        const newComment = prompt("Измените комментарий:", note.comment || '')
        if (newComment === null) return // пользователь отменил
        
        try {
            const response = await fetch(`http://localhost:3000/notes/${note.id}`, {
                method: "PUT",
                headers: { 
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ 
                    title: newTitle,
                    comment: newComment
                })
            })
            
            if (!response.ok) {
                throw new Error('Ошибка при обновлении заметки')
            }
            
            const updatedNote = await response.json()
            
            // Обновляем заметку в локальном хранилище
            if (this.view) {
                this.view.updateNoteInCache(updatedNote)
            }
            
            // Обновляем UI
            await this.loadNotes()
            
            // Закрываем старый попап и открываем новый с обновленными данными
            if (popup && popup.parentNode) {
                document.body.removeChild(popup)
            }
            
            // Показываем обновленный попап
            setTimeout(() => this.showNotePopup(updatedNote), 100)
            
            alert("✅ Заметка обновлена!")
            
        } catch (error) {
            console.error("Ошибка редактирования заметки:", error)
            alert(`Ошибка: ${error.message}`)
        }
    }

    showBookmarkPopup(bookmark) {
        const popup = document.createElement('div')
        popup.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            z-index: 10001;
            min-width: 350px;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
            font-family: system-ui, sans-serif;
        `
        
        popup.innerHTML = `
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 8px 0; color: #333; font-size: 18px;">✏️ Редактировать закладку</h3>
                <div style="color: #666; font-size: 13px; margin-bottom: 15px;">
                    Позиция: ${Math.round((bookmark.position || 0) * 100)}%
                </div>
            </div>
            
            <div style="margin-bottom: 25px;">
                <label style="display: block; margin-bottom: 8px; font-size: 14px; color: #555;">
                    Название закладки:
                </label>
                <input type="text" id="bookmark-title-input" 
                    value="${bookmark.title || 'Закладка'}"
                    style="
                        width: 100%;
                        padding: 12px;
                        border: 2px solid #ddd;
                        border-radius: 6px;
                        font-size: 15px;
                        box-sizing: border-box;
                        transition: border-color 0.3s;
                    "
                    placeholder="Введите название закладки"
                >
            </div>
            
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 25px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            ">
                <div style="color: #666; font-size: 13px;">
                    ${bookmark.created_at ? 'Создано: ' + new Date(bookmark.created_at).toLocaleDateString('ru-RU') : ''}
                </div>
                <div style="display: flex; gap: 10px;">
                    <button id="save-bookmark" style="
                        padding: 8px 20px;
                        background: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 500;
                    ">Сохранить</button>
                    <button id="close-bookmark-popup" style="
                        padding: 8px 20px;
                        background: #666;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Отмена</button>
                </div>
            </div>
        `
        
        document.body.appendChild(popup)
        
        // Фокус на поле ввода
        setTimeout(() => {
            const input = popup.querySelector('#bookmark-title-input')
            input.focus()
            input.select()
        }, 100)
        
        // КНОПКА СОХРАНЕНИЯ
        popup.querySelector('#save-bookmark').addEventListener('click', () => {
            const newTitle = popup.querySelector('#bookmark-title-input').value.trim()
            if (newTitle) {
                this.editBookmark(bookmark.id, newTitle, popup)
            } else {
                alert('Название не может быть пустым')
            }
        })
        
        // Сохранение по Enter
        popup.querySelector('#bookmark-title-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const newTitle = popup.querySelector('#bookmark-title-input').value.trim()
                if (newTitle) {
                    this.editBookmark(bookmark.id, newTitle, popup)
                }
            }
        })
        
        // КНОПКА ЗАКРЫТИЯ
        popup.querySelector('#close-bookmark-popup').addEventListener('click', () => {
            document.body.removeChild(popup)
        })

        popup.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.body.removeChild(popup)
            }
            // Останавливаем всплытие
            e.stopPropagation()
        })

        // Для всех полей ввода внутри попапа:
        popup.querySelectorAll('input, textarea, button').forEach(element => {
            element.addEventListener('keydown', (e) => e.stopPropagation())
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

    async editBookmark(bookmarkId, newTitle, popup) {
        try {
            const response = await fetch(`http://localhost:3000/bookmarks/${bookmarkId}`, {
                method: "PUT",
                headers: { 
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ 
                    title: newTitle.trim()
                })
            })
            
            if (!response.ok) {
                throw new Error('Ошибка при обновлении закладки')
            }
            
            // Обновляем список закладок
            await this.loadBookmarks()
            
            // Закрываем попап
            if (popup && popup.parentNode) {
                document.body.removeChild(popup)
            }
            
            // Показываем уведомление вместо alert
            this.showNotification('✅ Закладка обновлена!', 'success')
            
        } catch (error) {
            console.error("Ошибка редактирования закладки:", error)
            this.showNotification(`❌ Ошибка: ${error.message}`, 'error')
        }
    }


    showNotification(message, type = 'info') {
        const stack = new Error().stack
        console.group('🔔 Notification called:')
        console.log('Message:', message)
        console.log('Type:', type)
        console.log('Stack trace:', stack)
        console.groupEnd()

         
        this.#notificationStack.push({
            message,
            type,
            time: Date.now(),
            stack: stack.split('\n').slice(2, 6).join('\n') // Берем первые 4 строки стека
        })
        
        // Если за последние 500мс было такое же сообщение - пропускаем
        // const lastNotification = this.#notificationStack
        //     .slice(-5)
        //     .find(n => n.message === message && Date.now() - n.time < 500)
        
        // if (lastNotification) {
        //     console.log('🚫 Duplicate notification blocked:', message)
        //     return
        // }
        // Добавляем CSS стили один раз при первом вызове
        if (!window.diglibNotificationStylesAdded) {
            const style = document.createElement('style')
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                
                @keyframes fadeOut {
                    from {
                        opacity: 1;
                    }
                    to {
                        opacity: 0;
                    }
                }
                
                .diglib-notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    color: white;
                    border-radius: 6px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 10002;
                    font-size: 14px;
                    animation: slideIn 0.3s ease, fadeOut 0.3s ease 2.7s;
                }
            `
            document.head.appendChild(style)
            window.diglibNotificationStylesAdded = true
        }
        
        const notification = document.createElement('div')
        notification.className = 'diglib-notification'
        
        // Устанавливаем цвет в зависимости от типа
        let bgColor
        switch(type) {
            case 'success':
                bgColor = '#4CAF50'
                break
            case 'error':
                bgColor = '#f44336'
                break
            case 'warning':
                bgColor = '#ff9800'
                break
            default:
                bgColor = '#2196F3'
        }
        
        notification.style.backgroundColor = bgColor
        notification.innerHTML = message
        
        document.body.appendChild(notification)
        
        // Автоматическое скрытие через 3 секунды
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'fadeOut 0.3s ease'
                setTimeout(() => {
                    if (notification.parentNode) {
                        document.body.removeChild(notification)
                    }
                }, 300)
            }
        }, 3000)
        
        // Возвращаем элемент для возможности ручного управления
        return notification
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

showBookmarkCreationPopup() {
    console.log('showBookmarkCreationPopup called', new Date().getTime())

    if (!this.view?.lastLocation || !this.#bookId) {
        this.showNotification('Книга не загружена', 'error')
        return
    }
    
    const popup = document.createElement('div')
    popup.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 25px;
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 10001;
        min-width: 350px;
        max-width: 500px;
        font-family: system-ui, sans-serif;
    `
    
    popup.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h3 style="margin: 0 0 8px 0; color: #333; font-size: 18px;">🔖 Создать закладку</h3>
            <div style="color: #666; font-size: 13px;">
                Текущая позиция: ${Math.round((this.view.lastLocation.fraction || 0) * 100)}%
            </div>
        </div>
        
        <div style="margin-bottom: 25px;">
            <label style="display: block; margin-bottom: 8px; font-size: 14px; color: #555;">
                Название закладки:
            </label>
            <input type="text" id="new-bookmark-title" 
                value="Моя закладка"
                style="
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #ddd;
                    border-radius: 6px;
                    font-size: 15px;
                    box-sizing: border-box;
                "
                placeholder="Введите название закладки"
            >
        </div>
        
        <div style="
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 25px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        ">
            <button id="create-bookmark" style="
                padding: 10px 24px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
            ">Сохранить</button>
            <button id="close-bookmark-creation-popup" style="
                padding: 10px 24px;
                background: #666;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            ">Отмена</button>
        </div>
    `
    
    document.body.appendChild(popup)
    let isPopupClosed = false
    const outsideClickHandler = (e) => {
        if (!popup.contains(e.target)) {
            closePopup()
        }
    }

    const closePopup = () => {
        if (isPopupClosed) return
        isPopupClosed = true
        
        if (popup.parentNode) {
            document.body.removeChild(popup)
        }
        
        // Убираем обработчики
        document.removeEventListener('click', outsideClickHandler)
    }
    // Фокус на поле ввода
    setTimeout(() => {
        const input = popup.querySelector('#new-bookmark-title')
        input.focus()
        input.select()
    }, 100)
    
    let isSaving = false
    // КНОПКА СОХРАНЕНИЯ
    popup.querySelector('#create-bookmark').addEventListener('click', async () => {
        // ЗАЩИТА ОТ ПОВТОРНЫХ НАЖАТИЙ
        if (isSaving) {
            console.log('⚠️ Already saving, ignoring click')
            return
        }
        isSaving = true
        
        console.log('🎯 Bookmark save button clicked (first time)')
        
        const title = popup.querySelector('#new-bookmark-title').value.trim()
        if (!title) {
            this.showNotification('Введите название закладки!', 'error')
            isSaving = false
            return
        }
        
        const pos = this.view.lastLocation.fraction
        
        try {
            const response = await fetch(`http://localhost:3000/bookmarks/${this.#bookId}`, {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ 
                    title, 
                    position: pos 
                })
            })
            
            if (!response.ok) {
                throw new Error('Ошибка при создании закладки')
            }
            
            const result = await response.json()
            console.log('📝 Bookmark created successfully:', result)
            
            // Закрываем попап ПЕРЕД уведомлением
            closePopup()
            
            // ТОЛЬКО ОДИН ВЫЗОВ
            console.log('📢 Calling notification...')
            this.showNotification('✅ Закладка сохранена!', 'success')
            
            // Обновляем список
            await this.loadBookmarks()
            
        } catch (error) {
            console.error("❌ Bookmark creation error:", error)
            this.showNotification(`❌ Ошибка: ${error.message}`, 'error')
            isSaving = false // Сбрасываем флаг при ошибке
        }
    })
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
                <button data-id="${b.id}" class="edit" title="Редактировать">✏️</button>
                <button data-id="${b.id}" class="del" title="Удалить">❌</button>
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
        if (e.target.classList.contains("edit")) {
            const bookmarkId = e.target.dataset.id
            // Находим закладку в массиве
            const bookmark = bookmarks.find(b => b.id == bookmarkId)
            if (bookmark) {
                this.showBookmarkPopup(bookmark)
            }
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
    
    const selectedText = this.getSelectedText()
    if (!selectedText) {
        this.showNotification('Выделите текст для заметки!', 'error')
        return
    }
    if (selectedText.length > 3000) {
        this.showNotification('Текст слишком длинный (максимум 3000 символов)', 'error')
        return
    }
    
    const pos = this.view.lastLocation.fraction
    const selectionCFI = this.getSelectionCFI()
    const cfi = selectionCFI || this.view.lastLocation.cfi
    
    // Используем попап вместо prompt
    this.showNoteCreationPopup({
        title: selectedText.substring(0, 30),
        selected_text: selectedText,
        position: pos,
        cfi: cfi
    })
}

// Добавляем метод для попапа создания заметки
showNoteCreationPopup(noteData) {
    const popup = document.createElement('div')
    popup.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 25px;
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 10001;
        min-width: 400px;
        max-width: 600px;
        max-height: 80vh;
        overflow-y: auto;
        font-family: system-ui, sans-serif;
    `
    
    popup.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h3 style="margin: 0 0 8px 0; color: #333; font-size: 18px;">📝 Создать заметку</h3>
            <div style="color: #666; font-size: 13px;">
                Позиция: ${Math.round((noteData.position || 0) * 100)}%
            </div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 8px; font-size: 14px; color: #555;">
                Название заметки:
            </label>
            <input type="text" id="note-title-input" 
                value="${noteData.title || ''}"
                style="
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #ddd;
                    border-radius: 6px;
                    font-size: 15px;
                    box-sizing: border-box;
                    margin-bottom: 20px;
                "
                placeholder="Введите название заметки"
            >
            
            <label style="display: block; margin-bottom: 8px; font-size: 14px; color: #555;">
                Комментарий (необязательно):
            </label>
            <textarea id="note-comment-input" 
                style="
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #ddd;
                    border-radius: 6px;
                    font-size: 15px;
                    box-sizing: border-box;
                    min-height: 80px;
                    resize: vertical;
                    font-family: inherit;
                "
                placeholder="Введите комментарий к заметке"
            ></textarea>
        </div>
        
        <div style="
            margin-bottom: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 6px;
        ">
            <div style="font-size: 14px; color: #666; margin-bottom: 8px;">
                <strong>Выделенный текст:</strong>
            </div>
            <div style="
                font-size: 14px;
                color: #555;
                line-height: 1.5;
                max-height: 100px;
                overflow-y: auto;
                padding: 8px;
                background: white;
                border-radius: 4px;
            ">
                ${noteData.selected_text || ''}
            </div>
        </div>
        
        <div style="
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 25px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        ">
            <button id="save-note" style="
                padding: 10px 24px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
            ">Сохранить заметку</button>
            <button id="close-note-popup" style="
                padding: 10px 24px;
                background: #666;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            ">Отмена</button>
        </div>
    `
    
    document.body.appendChild(popup)
    
    // Фокус на поле названия
    setTimeout(() => {
        const input = popup.querySelector('#note-title-input')
        input.focus()
        input.select()
    }, 100)
    
    // КНОПКА СОХРАНЕНИЯ
    popup.querySelector('#save-note').addEventListener('click', async () => {
        const title = popup.querySelector('#note-title-input').value.trim()
        const comment = popup.querySelector('#note-comment-input').value.trim()
        
        if (!title) {
            this.showNotification('Введите название заметки!', 'error')
            return
        }
        
        try {
            const response = await fetch(`http://localhost:3000/notes/${this.#bookId}`, {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ 
                    title,
                    position: noteData.position,
                    text: noteData.selected_text,
                    selected_text: noteData.selected_text,
                    comment: comment,
                    cfi: noteData.cfi,
                    color: 'yellow' 
                })
            })
            
            if (!response.ok) {
                throw new Error('Ошибка при создании заметки')
            }
            
            const createdNote = await response.json()
            
            if (createdNote.id && this.view?.addNoteHighlight) {
                await this.view.addNoteHighlight(createdNote)
            }
            
            // Обновляем список
            await this.loadNotes()
            
            // Закрываем попап
            document.body.removeChild(popup)
            
            this.showNotification('✅ Заметка сохранена!', 'success')
            
        } catch (error) {
            console.error("Ошибка создания заметки:", error)
            this.showNotification(`❌ Ошибка: ${error.message}`, 'error')
        }
    })
    
    // КНОПКА ЗАКРЫТИЯ
    popup.querySelector('#close-note-popup').addEventListener('click', () => {
        document.body.removeChild(popup)
    })
    
    popup.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.body.removeChild(popup)
        }
        // ОСТАНАВЛИВАЕМ ВСПЛЫТИЕ КЛАВИШ
        e.stopPropagation()
    })
    
    // ОСТАНАВЛИВАЕМ ВСПЛЫТИЕ ДЛЯ ВСЕХ ЭЛЕМЕНТОВ ВВОДА
    const stopPropagation = (e) => e.stopPropagation()
    popup.querySelector('#note-title-input').addEventListener('keydown', stopPropagation)
    popup.querySelector('#note-comment-input').addEventListener('keydown', stopPropagation)
    
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
            }, 1000)
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