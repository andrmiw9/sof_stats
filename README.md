Заметки:

- В пункте 1) упоминается про наличие корректной поддержки русского языка. Мой сервис поддерживает русский язык, но вот
  StackOverflow не поддерживает русские теги, насколько я понял.
- Если один из тегов не буквы-цифры, то выкидывается ошибка. Альтернатива - выкинуть тег и искать по всем остальным,
  если они нормальные, но из-за формата ответа я не знаю как передать сообщение о неправильном теги => тот, кто
  запрашивал даже не узнает, что в теге вообще-то была ошибка.
- Если в переменных окружения (среды) есть HTTP_PROXY, то для запросов будет использоваться она.
- 