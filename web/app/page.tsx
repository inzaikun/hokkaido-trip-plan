import { itinerary } from "./itinerary-data";

const typeClass: Record<string, string> = {
  移動: "move",
  観光: "see",
  昼食: "food",
  夕食: "food",
  朝食: "food",
  休憩: "rest",
  手続き: "prep",
  準備: "prep",
};

export default function Page() {
  const totalStops = itinerary.days.reduce((sum, day) => sum + day.timeline.length, 0);
  const restaurantCount = itinerary.days.reduce((sum, day) => sum + day.restaurants.length, 0);

  return (
    <main>
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">HOKKAIDO FAMILY TRAVEL GUIDE</p>
          <h1>{itinerary.title}</h1>
          <p className="period">{itinerary.period}</p>
          <p className="lead">
            洞爺湖、札幌、富良野・美瑛、層雲峡、中標津、帯広をめぐる時刻ベースの旅行ガイド。
            PowerPoint版の原稿と同じMarkdownから生成しています。
          </p>
          <div className="hero__actions">
            <a href="#days">日別ガイドを見る</a>
            <a href="https://github.com/inzaikun/hokkaido-trip-plan/tree/main/itinerary/days">Markdownを編集</a>
          </div>
        </div>
        <div className="hero__panel">
          <div>
            <span>{itinerary.days.length}</span>
            <p>days</p>
          </div>
          <div>
            <span>{totalStops}</span>
            <p>schedule items</p>
          </div>
          <div>
            <span>{restaurantCount}</span>
            <p>restaurant ideas</p>
          </div>
        </div>
      </section>

      <section className="route">
        <h2>旅の流れ</h2>
        <div className="route__rail">
          {itinerary.days.map((day) => (
            <a href={`#day-${day.date}`} key={day.date}>
              <strong>Day {day.day}</strong>
              <span>{day.area}</span>
            </a>
          ))}
        </div>
      </section>

      <section className="days" id="days">
        {itinerary.days.map((day) => (
          <article className="day" id={`day-${day.date}`} key={day.date}>
            <header className="day__header">
              <div>
                <p className="day__meta">DAY {day.day} / {day.date}</p>
                <h2>{day.title}</h2>
                <p className="area">{day.area}</p>
              </div>
              <div className="photo">
                <span>{day.hero}</span>
              </div>
            </header>
            <p className="summary">{day.summary}</p>

            <div className="day__grid">
              <section className="card">
                <h3>時刻ベース詳細スケジュール</h3>
                <ol className="timeline">
                  {day.timeline.map((item) => (
                    <li key={`${day.date}-${item.time}-${item.detail}`}>
                      <time>{item.time}</time>
                      <span className={`tag ${typeClass[item.type] ?? "other"}`}>{item.type}</span>
                      <div>
                        <strong>{item.place}</strong>
                        <p>{item.detail}</p>
                        <small>{item.duration}</small>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <aside className="side">
                <section className="card">
                  <h3>レストラン候補</h3>
                  <div className="restaurants">
                    {day.restaurants.map((restaurant) => (
                      <div key={`${day.date}-${restaurant.meal}-${restaurant.name}`}>
                        <span>{restaurant.meal}</span>
                        <strong>{restaurant.name}</strong>
                        <p>{restaurant.area} / {restaurant.memo}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {day.notes.length > 0 ? (
                  <section className="card memo">
                    <h3>メモ</h3>
                    <ul>
                      {day.notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </section>
                ) : null}
              </aside>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
