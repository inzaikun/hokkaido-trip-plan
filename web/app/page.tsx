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

function shortText(text: string, limit = 82) {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).replace(/[、。・\s]+$/, "")}…`;
}

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
            洞爺湖、札幌、富良野・美瑛、層雲峡、中標津、帯広へ。
            出発前にめくりたくなる、家族旅行のための北海道ガイドです。
          </p>
          <div className="hero__actions">
            <a href="#days">日別ガイドを見る</a>
            <a href="https://github.com/inzaikun/hokkaido-trip-plan/raw/main/output/hokkaido-family-travel-guide.pdf">PDFを見る</a>
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

      <section className="insideCover" aria-label="表紙裏">
        <img src="/images/inside-cover.jpg" alt="北海道の空と草原" />
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
                {day.heroPhoto?.image ? (
                  <img src={`/images/${day.heroPhoto.image}`} alt={day.heroPhoto.place || day.hero} />
                ) : (
                  <span>{day.hero}</span>
                )}
              </div>
            </header>
            <div className="guideIntro">
              <section className="routeCard">
                <div className="cardTitleRow">
                  <h3>Today&apos;s Map</h3>
                  <a href={day.routeMapUrl} target="_blank" rel="noreferrer">Google Map</a>
                </div>
                <div className="routeCardBody">
                  <div className="sketchMap" aria-label="簡易ルートマップ">
                    <img src={day.routeMapImage} alt={`${day.area}のルート地図`} />
                  </div>
                  <ol>
                    {day.route.map((point) => (
                    <li key={`${day.date}-${point.place}-${point.note}`}>
                      <strong>{point.place}</strong>
                      {point.note ? <span>{point.note}</span> : null}
                      {point.leg ? <small>{point.leg}</small> : null}
                    </li>
                    ))}
                  </ol>
                </div>
              </section>
              <section className="themeCard">
                <h3>Today&apos;s Theme</h3>
                <p>{day.todayTheme}</p>
              </section>
            </div>

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
                        <p title={item.detail}>{shortText(item.detail, 86)}</p>
                        <small>{item.duration}</small>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <aside className="side">
                <section className="card">
                  <h3>今日の食事メモ</h3>
                  <div className="restaurants">
                    {day.mealRecommendations.map((restaurant) => (
                      <div key={`${day.date}-${restaurant.label}-${restaurant.name}`}>
                        <span>{restaurant.label}</span>
                        <strong>{restaurant.name}</strong>
                        <em>{restaurant.stars}</em>
                        <p>{restaurant.budget} / {restaurant.popular}</p>
                        <p>{shortText(restaurant.memo, 48)}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {day.guideSpots.length > 0 ? (
                  <section className="card sideTrip">
                    <h3>より道スポット</h3>
                    {day.guideSpots.slice(0, 1).map((spot) => (
                      <figure key={`${day.date}-${spot.place}`}>
                        {spot.image ? (
                          <img src={`/images/${spot.image}`} alt={spot.place} />
                        ) : (
                          <div className="photoSpots__placeholder">{spot.place}</div>
                        )}
                        <figcaption>
                          <strong>{spot.place}</strong>
                          <span>{shortText(spot.caption, 64)}</span>
                          <small>滞在 {spot.stay} / {spot.parking}</small>
                          <a href={spot.map_url} target="_blank" rel="noreferrer">Google Map</a>
                        </figcaption>
                      </figure>
                    ))}
                  </section>
                ) : null}

                {day.todaysTips.length > 0 ? (
                  <section className="card memo">
                    <h3>Today&apos;s Tips</h3>
                    <ul>
                      {day.todaysTips.map((note) => (
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
