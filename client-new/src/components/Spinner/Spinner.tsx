import styles from './Spinner.module.css';

export default function Spinner() {
  return (
    <div className={styles.spinner}>
      <div className={styles.dot} />
      <div className={styles.dot} />
      <div className={styles.dot} />
    </div>
  );
}
